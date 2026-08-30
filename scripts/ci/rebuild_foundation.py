#!/usr/bin/env python3
"""Run two isolated frozen-lock builds and compare their complete normalized outputs."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import build_foundation_artifact

ROOT = Path(__file__).resolve().parents[2]
BUILD_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("uv", "sync", "--frozen", "--all-groups", "--all-packages"),
    ("corepack", "pnpm", "install", "--frozen-lockfile"),
    ("corepack", "pnpm", "build"),
    ("uv", "build", "--all-packages"),
)
FORBIDDEN_CLEAN_BUILD_PARTS = {".next", ".pnpm-store", ".venv", "dist", "node_modules"}


class ReproducibilityError(RuntimeError):
    """A clean-build or byte-reproducibility invariant failed."""


@dataclass(frozen=True)
class BuildRecord:
    label: str
    workspace_root: str
    clean_start: bool
    commands: tuple[str, ...]
    build_id: str
    preview_seed_sha256: str
    workspace_path_canonicalization: str
    generated_file_count: int
    generated_sha256: str
    archive_sha256: str
    log_sha256: str


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_paths(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    relative_paths = [Path(value.decode()) for value in result.stdout.split(b"\0") if value]
    paths = [
        path for path in relative_paths if (root / path).is_file() or (root / path).is_symlink()
    ]
    return sorted(paths, key=lambda path: path.as_posix().encode("utf-8"))


def source_identity(root: Path, paths: list[Path]) -> str:
    digest = hashlib.sha256(b"wp01-reproducibility-input-v2\0")
    for relative in paths:
        path = root / relative
        digest.update(relative.as_posix().encode("utf-8") + b"\0")
        if path.is_symlink():
            digest.update(b"symlink\0" + os.readlink(path).encode("utf-8") + b"\0")
            continue
        mode = b"executable" if path.stat().st_mode & stat.S_IXUSR else b"file"
        digest.update(mode + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def copy_source(root: Path, destination: Path, paths: list[Path]) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    for relative in paths:
        source = root / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            target.symlink_to(os.readlink(source))
        else:
            shutil.copy2(source, target)


def seed_deterministic_next_inputs(workspace: Path, identity: str) -> dict[str, str]:
    """Seed build-only Next entropy from the public source identity."""

    def digest(label: str) -> str:
        return hashlib.sha256(f"wp01:{label}:{identity}".encode()).hexdigest()

    cache = workspace / "apps" / "web" / ".next" / "cache"
    cache.mkdir(parents=True)
    preview = {
        "previewModeId": digest("preview-id")[:32],
        "previewModeSigningKey": digest("preview-signing"),
        "previewModeEncryptionKey": digest("preview-encryption"),
        "expireAt": 253402300799000,
    }
    (cache / ".previewinfo").write_text(
        json.dumps(preview, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    server_actions = base64.b64encode(
        hashlib.sha256(f"wp01:server-actions:{identity}".encode()).digest()
    ).decode("ascii")
    return {
        "next_build_id": f"wp01-{identity}",
        "next_server_actions_encryption_key": server_actions,
        "preview_seed_sha256": sha256_file(cache / ".previewinfo"),
    }


def assert_clean_start(workspace: Path) -> None:
    offenders = sorted(
        path.relative_to(workspace).as_posix()
        for path in workspace.rglob("*")
        if path.name in FORBIDDEN_CLEAN_BUILD_PARTS
    )
    if offenders:
        raise ReproducibilityError(
            f"isolated workspace contains pre-build/generated state: {offenders}"
        )


def run_command(
    command: tuple[str, ...], workspace: Path, environment: dict[str, str], log: Path
) -> None:
    with log.open("a", encoding="utf-8") as stream:
        stream.write(f"$ {shlex.join(command)}\n")
        stream.flush()
        result = subprocess.run(
            command,
            cwd=workspace,
            env=environment,
            check=False,
            stdout=stream,
            stderr=subprocess.STDOUT,
            text=True,
        )
        stream.write(f"exit_code={result.returncode}\n")
    if result.returncode:
        raise ReproducibilityError(f"{shlex.join(command)} failed in {workspace.name}; see {log}")


def generated_paths(workspace: Path) -> list[Path]:
    result: list[Path] = []
    next_root = workspace / "apps" / "web" / ".next"
    if next_root.exists():
        result.extend(
            path
            for path in next_root.rglob("*")
            if (path.is_file() or path.is_symlink())
            and build_foundation_artifact.included_from(workspace, path)
        )
    for parent in (workspace / "services", workspace / "packages"):
        if not parent.exists():
            continue
        result.extend(
            path for path in parent.rglob("dist/*") if path.is_file() or path.is_symlink()
        )
    return sorted(
        set(result), key=lambda path: path.relative_to(workspace).as_posix().encode("utf-8")
    )


def file_manifest(root: Path, paths: list[Path]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            entries.append({"path": relative, "type": "symlink", "target": os.readlink(path)})
        else:
            payload = build_foundation_artifact.canonical_payload(root, path)
            entries.append(
                {
                    "path": relative,
                    "type": "file",
                    "mode": "0755" if path.stat().st_mode & stat.S_IXUSR else "0644",
                    "size": len(payload),
                    "sha256": sha256_bytes(payload),
                }
            )
    return entries


def manifest_identity(entries: list[dict[str, Any]]) -> str:
    payload = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(payload)


def build_normalized_artifact(
    workspace: Path, output: Path, manifest: Path, environment: dict[str, str], log: Path
) -> None:
    command = (
        sys.executable,
        str(workspace / "scripts" / "ci" / "build_foundation_artifact.py"),
        "--root",
        str(workspace),
        "--output",
        str(output),
        "--manifest",
        str(manifest),
    )
    run_command(command, workspace, environment, log)


def execute_build(
    *,
    label: str,
    root: Path,
    workspace_parent: Path,
    artifact_dir: Path,
    paths: list[Path],
    environment: dict[str, str],
) -> BuildRecord:
    workspace = workspace_parent / label
    copy_source(root, workspace, paths)
    assert_clean_start(workspace)
    deterministic_inputs = seed_deterministic_next_inputs(
        workspace, environment["WP01_INPUT_IDENTITY"]
    )
    if environment["NEXT_BUILD_ID"] != deterministic_inputs["next_build_id"]:
        raise ReproducibilityError(f"{label} Next build ID does not match its source identity")
    environment = environment | {
        "NEXT_SERVER_ACTIONS_ENCRYPTION_KEY": deterministic_inputs[
            "next_server_actions_encryption_key"
        ]
    }
    log = artifact_dir / f"{label}.log"
    log.write_text(
        "$ seed deterministic Next preview and server-action build entropy\n"
        f"preview_seed_sha256={deterministic_inputs['preview_seed_sha256']}\n"
        "workspace_path_canonicalization=<isolated-workspace> -> /workspace\n"
        "exit_code=0\n",
        encoding="utf-8",
    )
    commands: list[str] = []
    for command in BUILD_COMMANDS:
        run_command(command, workspace, environment, log)
        commands.append(shlex.join(command))

    build_id_path = workspace / "apps" / "web" / ".next" / "BUILD_ID"
    if not build_id_path.is_file():
        raise ReproducibilityError(f"{label} did not produce the Next BUILD_ID")
    build_id = build_id_path.read_text(encoding="utf-8").strip()

    generated = file_manifest(workspace, generated_paths(workspace))
    if not generated:
        raise ReproducibilityError(f"{label} produced no generated artifacts")
    generated_manifest = artifact_dir / f"{label}.generated.json"
    generated_manifest.write_text(
        json.dumps(generated, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    archive = artifact_dir / f"{label}.tar.gz"
    archive_manifest = artifact_dir / f"{label}.manifest.json"
    build_normalized_artifact(workspace, archive, archive_manifest, environment, log)
    commands.append("build_foundation_artifact.py --root <isolated-workspace>")
    return BuildRecord(
        label=label,
        workspace_root=str(workspace.resolve()),
        clean_start=True,
        commands=tuple(commands),
        build_id=build_id,
        preview_seed_sha256=deterministic_inputs["preview_seed_sha256"],
        workspace_path_canonicalization="/workspace",
        generated_file_count=len(generated),
        generated_sha256=manifest_identity(generated),
        archive_sha256=sha256_file(archive),
        log_sha256=sha256_file(log),
    )


def verify_independent_builds(records: tuple[BuildRecord, ...]) -> None:
    if len(records) != 2:
        raise ReproducibilityError("exactly two build records are required")
    if len({record.workspace_root for record in records}) != 2:
        raise ReproducibilityError(
            "archive-twice is not reproducibility: builds must use distinct clean workspaces"
        )
    if not all(record.clean_start for record in records):
        raise ReproducibilityError("both builds must start without dependencies or generated state")
    expected_commands = tuple(shlex.join(command) for command in BUILD_COMMANDS)
    for record in records:
        if record.commands[: len(expected_commands)] != expected_commands:
            raise ReproducibilityError(f"{record.label} did not execute every frozen build command")
    if len({record.build_id for record in records}) != 1:
        raise ReproducibilityError("Next build identities differ")
    if len({record.preview_seed_sha256 for record in records}) != 1:
        raise ReproducibilityError("Next deterministic preview inputs differ")
    if {record.workspace_path_canonicalization for record in records} != {"/workspace"}:
        raise ReproducibilityError("isolated workspace paths were not canonically normalized")
    if len({record.generated_sha256 for record in records}) != 1:
        raise ReproducibilityError("complete generated artifact manifests differ")
    if len({record.archive_sha256 for record in records}) != 1:
        raise ReproducibilityError("normalized foundation archives differ")


def source_date_epoch(root: Path) -> int:
    configured = os.environ.get("SOURCE_DATE_EPOCH")
    if configured:
        return int(configured)
    result = subprocess.run(
        ["git", "show", "-s", "--format=%ct", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return int(result.stdout.strip())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, default=Path("artifacts/reproducibility"))
    parser.add_argument("--workspace-parent", type=Path)
    args = parser.parse_args()

    artifact_dir = args.artifact_dir.resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    workspace_parent = (
        args.workspace_parent.resolve()
        if args.workspace_parent
        else Path(tempfile.mkdtemp(prefix="wp01-repro-builds-"))
    )
    workspace_parent.mkdir(parents=True, exist_ok=True)
    paths = source_paths(ROOT)
    identity = source_identity(ROOT, paths)
    epoch = source_date_epoch(ROOT)
    next_build_id = f"wp01-{identity}"
    environment = os.environ.copy()
    environment.pop("VIRTUAL_ENV", None)
    environment.update(
        {
            "ALLOW_MODEL_REQUESTS": "false",
            "CI": "true",
            "LC_ALL": "C",
            "NEXT_BUILD_ID": next_build_id,
            "NEXT_TELEMETRY_DISABLED": "1",
            "PYDANTIC_AI_ALLOW_MODEL_REQUESTS": "false",
            "PYTHONHASHSEED": "0",
            "SOURCE_DATE_EPOCH": str(epoch),
            "TZ": "UTC",
            "UV_PROJECT_ENVIRONMENT": ".venv",
            "WP01_INPUT_IDENTITY": identity,
        }
    )

    records = tuple(
        execute_build(
            label=label,
            root=ROOT,
            workspace_parent=workspace_parent,
            artifact_dir=artifact_dir,
            paths=paths,
            environment=environment,
        )
        for label in ("build-a", "build-b")
    )
    verify_independent_builds(records)
    if (artifact_dir / "build-a.generated.json").read_bytes() != (
        artifact_dir / "build-b.generated.json"
    ).read_bytes():
        raise ReproducibilityError("generated artifact manifests are not byte-identical")
    if (artifact_dir / "build-a.tar.gz").read_bytes() != (
        artifact_dir / "build-b.tar.gz"
    ).read_bytes():
        raise ReproducibilityError("foundation archives are not byte-identical")

    checksums = {
        "schema_version": 2,
        "algorithm": "sha256",
        "input_identity": identity,
        "source_date_epoch": epoch,
        "next_build_id": next_build_id,
        "workspace_path_canonicalization": "/workspace",
        "next_random_build_inputs": "deterministically derived from input_identity",
        "artifacts": {
            "build-a.tar.gz": records[0].archive_sha256,
            "build-b.tar.gz": records[1].archive_sha256,
            "build-a.generated.json": sha256_file(artifact_dir / "build-a.generated.json"),
            "build-b.generated.json": sha256_file(artifact_dir / "build-b.generated.json"),
        },
        "independent_clean_builds": True,
        "generated_artifacts_byte_identical": True,
        "normalized_archives_byte_identical": True,
    }
    (artifact_dir / "checksums.json").write_text(
        json.dumps(checksums, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    provenance_records = []
    for record in records:
        value = asdict(record)
        value["workspace_root"] = f"<temporary>/{record.label}"
        provenance_records.append(value)
    provenance = {
        "schema_version": 1,
        "input_identity": identity,
        "source_date_epoch": epoch,
        "next_build_id": next_build_id,
        "workspace_path_canonicalization": "/workspace",
        "next_random_build_inputs": "deterministically derived from input_identity",
        "builds": provenance_records,
        "result": "passed",
    }
    (artifact_dir / "build-provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        "PASS: two distinct clean frozen-lock builds produced "
        f"{records[0].generated_file_count} byte-identical generated files and "
        f"sha256:{records[0].archive_sha256}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReproducibilityError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
