#!/usr/bin/env python3
"""Fail closed on mutable dependency declarations or alternate package managers."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EXCLUDED_PARTS = {".git", ".next", ".venv", "node_modules", "docs", "agent", "artifacts"}
MUTABLE_NODE_PREFIXES = ("^", "~", ">", "<", "latest", "next", "beta", "alpha", "rc")
BOUNDED_PEER_RANGE = re.compile(r"([~^]?)([0-9]+)[.]([0-9]+)[.]([0-9]+)")
LEGACY_POC_PACKAGE_LOCK_SHA256 = "5222d716a8480a61d417ec2efef1d5da44741f1c3d2a12ea87a778e3339650ff"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail(f"{path.relative_to(ROOT)} must contain a JSON object")
    return value


def production_package_jsons() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("package.json")
        if not any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts)
    )


def check_node() -> int:
    root_manifest = ROOT / "package.json"
    lock = ROOT / "pnpm-lock.yaml"
    workspace = ROOT / "pnpm-workspace.yaml"
    if not root_manifest.exists() or not lock.exists() or not workspace.exists():
        fail("package.json, pnpm-lock.yaml, and pnpm-workspace.yaml are all required")
    if (ROOT / "yarn.lock").exists() or (ROOT / "npm-shrinkwrap.json").exists():
        fail(
            "pnpm is the only allowed root Node package manager; "
            "alternate root lockfiles are forbidden"
        )
    legacy_lock = ROOT / "package-lock.json"
    if not legacy_lock.exists():
        fail("the preserved legacy POC package-lock.json is unexpectedly missing")
    legacy_digest = hashlib.sha256(legacy_lock.read_bytes()).hexdigest()
    if legacy_digest != LEGACY_POC_PACKAGE_LOCK_SHA256:
        fail("the preserved legacy POC package-lock.json changed or was regenerated")

    root = read_json(root_manifest)
    package_manager = root.get("packageManager", "")
    if not re.fullmatch(r"pnpm@10[.][0-9]+[.][0-9]+", package_manager):
        fail("root packageManager must pin pnpm 10 to an exact stable version")

    manifests = production_package_jsons()
    for manifest_path in manifests:
        manifest = read_json(manifest_path)
        for group in (
            "dependencies",
            "devDependencies",
            "optionalDependencies",
            "peerDependencies",
        ):
            dependencies = manifest.get(group, {})
            if not isinstance(dependencies, dict):
                fail(f"{manifest_path.relative_to(ROOT)} {group} must be an object")
            for name, version in dependencies.items():
                if not isinstance(version, str) or not version:
                    fail(f"{manifest_path.relative_to(ROOT)} has invalid version for {name}")
                if version.startswith("workspace:"):
                    continue
                lowered = version.lower()
                if group == "peerDependencies":
                    match = BOUNDED_PEER_RANGE.fullmatch(version)
                    dev_version = manifest.get("devDependencies", {}).get(name)
                    if (
                        not match
                        or not isinstance(dev_version, str)
                        or not re.fullmatch(r"[0-9]+[.][0-9]+[.][0-9]+", dev_version)
                    ):
                        fail(
                            f"{manifest_path.relative_to(ROOT)} peer {name} must use a bounded "
                            "exact/caret/tilde "
                            "range and have an exactly pinned devDependency compatibility target"
                        )
                    operator, major, minor, _ = match.groups()
                    dev_major, dev_minor, _ = dev_version.split(".")
                    if major != dev_major or (operator == "~" and minor != dev_minor):
                        fail(
                            f"{manifest_path.relative_to(ROOT)} peer range {name}={version} "
                            "does not contain "
                            f"its pinned compatibility target {dev_version}"
                        )
                    continue
                if lowered.startswith(MUTABLE_NODE_PREFIXES) or "*" in version or "||" in version:
                    fail(
                        f"{manifest_path.relative_to(ROOT)} has mutable {group} range "
                        f"{name}={version}"
                    )
                if version.startswith(("git+", "github:", "http:", "https:", "file:")):
                    fail(
                        f"{manifest_path.relative_to(ROOT)} uses unreviewed dependency source "
                        f"{name}={version}"
                    )

    lock_text = lock.read_text(encoding="utf-8")
    if "<<<<<<<" in lock_text or "lockfileVersion:" not in lock_text:
        fail("pnpm-lock.yaml is malformed or contains merge markers")
    return len(manifests)


def production_pyprojects() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("pyproject.toml")
        if not any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts)
    )


def check_python() -> int:
    pyproject_path = ROOT / "pyproject.toml"
    lock = ROOT / "uv.lock"
    if not pyproject_path.exists() or not lock.exists():
        fail("pyproject.toml and uv.lock are both required")
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    requires_python = pyproject.get("project", {}).get("requires-python", "")
    if requires_python != "==3.12.*":
        fail("root project.requires-python must pin the Python 3.12 minor line")

    uv_config = pyproject.get("tool", {}).get("uv", {})
    required_uv = uv_config.get("required-version", "") if isinstance(uv_config, dict) else ""
    if not re.fullmatch(r"==?[0-9]+[.][0-9]+[.][0-9]+", str(required_uv)):
        fail("tool.uv.required-version must pin uv to an exact stable version")

    dependencies: list[str] = []
    pyprojects = production_pyprojects()
    expected_members = {
        "packages/contracts_py",
        "packages/evals",
        "services/api",
        "services/worker_analysis",
        "services/worker_export",
    }
    configured_members = set(
        pyproject.get("tool", {}).get("uv", {}).get("workspace", {}).get("members", [])
    )
    if configured_members != expected_members:
        fail(f"tool.uv.workspace.members drifted: {sorted(configured_members)}")

    for member_path in pyprojects:
        member = tomllib.loads(member_path.read_text(encoding="utf-8"))
        member_requires_python = member.get("project", {}).get("requires-python", "")
        if member_requires_python != "==3.12.*":
            fail(f"{member_path.relative_to(ROOT)} must pin the Python 3.12 minor line")
        project = member.get("project", {})
        dependencies.extend(project.get("dependencies", []))
        optional = project.get("optional-dependencies", {})
        if isinstance(optional, dict):
            for values in optional.values():
                dependencies.extend(values)
        groups = member.get("dependency-groups", {})
        if isinstance(groups, dict):
            for values in groups.values():
                dependencies.extend(value for value in values if isinstance(value, str))
        build_system = member.get("build-system", {})
        if isinstance(build_system, dict):
            dependencies.extend(build_system.get("requires", []))

    for dependency in dependencies:
        if not isinstance(dependency, str):
            fail("Python dependency declarations must be strings")
        if " @ " in dependency or dependency.startswith(("git+", "http:", "https:", "file:")):
            fail(f"unreviewed Python dependency source: {dependency}")
        if ";" in dependency:
            base, _ = dependency.split(";", 1)
        else:
            base = dependency
        if "==" not in base:
            fail(f"Python dependency is not exactly pinned: {dependency}")

    lock_text = lock.read_text(encoding="utf-8")
    if "<<<<<<<" in lock_text or "version = 1" not in lock_text:
        fail("uv.lock is malformed or contains merge markers")
    return len(dependencies)


def main() -> int:
    node_manifests = check_node()
    python_dependencies = check_python()
    print(
        f"PASS: pnpm-only lock policy, {node_manifests} Node manifest(s), "
        f"{python_dependencies} Python declaration(s), exact tool pins, and frozen legacy POC lock"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
