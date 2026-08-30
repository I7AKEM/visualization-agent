#!/usr/bin/env python3
"""Create a byte-reproducible WP-01 foundation artifact and checksum manifest."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import stat
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROOT_FILES = {
    ".gitattributes",
    ".gitignore",
    ".node-version",
    ".npmrc",
    ".nvmrc",
    ".python-version",
    "REPRODUCIBILITY.md",
    "SECURITY.md",
    "package.json",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
    "pyproject.toml",
    "uv.lock",
    "tsconfig.base.json",
    "vitest.workspace.ts",
}
ROOT_DIRS = (
    ".github",
    "apps",
    "services",
    "packages",
    "schemas",
    "scripts",
    "infra",
    "docs/evidence/wp-01",
)
EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "coverage",
    "artifacts",
}
EXCLUDED_BUILD_PATHS = {
    ".next/cache",
    ".next/trace",
    ".next/diagnostics",
}
CANONICAL_BUILD_ROOT = b"/workspace"


def included_from(root: Path, path: Path) -> bool:
    relative = path.relative_to(root)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if "node_modules" in relative.parts and not (
        ".next" in relative.parts and "standalone" in relative.parts
    ):
        return False
    if path.name.endswith(".tsbuildinfo"):
        return False
    normalized = relative.as_posix()
    return not any(excluded in normalized for excluded in EXCLUDED_BUILD_PATHS)


def included(path: Path) -> bool:
    return included_from(ROOT, path)


def candidates(root: Path = ROOT) -> list[Path]:
    paths: set[Path] = set()
    for name in ROOT_FILES:
        path = root / name
        if path.is_file():
            paths.add(path)
    for name in ROOT_DIRS:
        base = root / name
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if (path.is_file() or path.is_symlink()) and included_from(root, path):
                paths.add(path)
    return sorted(paths, key=lambda path: path.relative_to(root).as_posix().encode("utf-8"))


def source_date_epoch(root: Path = ROOT) -> int:
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_payload(root: Path, path: Path) -> bytes:
    """Normalize only the isolated workspace prefix embedded by build tooling."""

    workspace_prefix = root.resolve().as_posix().encode("utf-8")
    return path.read_bytes().replace(workspace_prefix, CANONICAL_BUILD_ROOT)


def build(root: Path, output: Path) -> list[dict[str, object]]:
    epoch = source_date_epoch(root)
    entries: list[dict[str, object]] = []
    output.parent.mkdir(parents=True, exist_ok=True)
    with (
        output.open("wb") as raw_output,
        gzip.GzipFile(
            filename="", mode="wb", compresslevel=9, fileobj=raw_output, mtime=0
        ) as gzipped,
        tarfile.open(fileobj=gzipped, mode="w", format=tarfile.PAX_FORMAT) as archive,
    ):
        for path in candidates(root):
            relative_path = path.relative_to(root)
            relative = relative_path.as_posix()
            information = tarfile.TarInfo(relative)
            information.uid = 0
            information.gid = 0
            information.uname = "root"
            information.gname = "root"
            information.mtime = epoch
            if path.is_symlink():
                target = os.readlink(path)
                normalized_target = Path(
                    os.path.normpath((relative_path.parent / target).as_posix())
                )
                if os.path.isabs(target) or (
                    normalized_target.parts and normalized_target.parts[0] == ".."
                ):
                    raise ValueError(
                        f"unsafe symlink in foundation artifact: {relative} -> {target}"
                    )
                information.type = tarfile.SYMTYPE
                information.linkname = target
                information.mode = 0o777
                information.size = 0
                archive.addfile(information)
                entries.append({"path": relative, "type": "symlink", "target": target})
                continue
            payload = canonical_payload(root, path)
            mode = path.stat().st_mode
            information.mode = 0o755 if mode & stat.S_IXUSR else 0o644
            information.size = len(payload)
            archive.addfile(information, io.BytesIO(payload))
            entries.append(
                {
                    "path": relative,
                    "type": "file",
                    "size": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
    return entries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    manifest_path = args.manifest.resolve()
    entries = build(root, output)
    manifest = {
        "schema_version": 1,
        "artifact": output.name,
        "artifact_sha256": sha256(output),
        "file_count": len(entries),
        "files": entries,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"sha256:{manifest['artifact_sha256']}  {output}")
    print(f"PASS: normalized {len(entries)} file(s) into a deterministic foundation artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
