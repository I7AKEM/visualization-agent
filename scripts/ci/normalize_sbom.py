#!/usr/bin/env python3
"""Remove generator randomness and normalize ordering in CycloneDX evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def component_key(component: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(component.get("purl", "")),
        str(component.get("name", "")),
        str(component.get("version", "")),
    )


def normalized_timestamp() -> str:
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "315532800"))
    return datetime.fromtimestamp(epoch, tz=UTC).isoformat().replace("+00:00", "Z")


def normalize_timestamps(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "timestamp":
                value[key] = normalized_timestamp()
            else:
                normalize_timestamps(child)
    elif isinstance(value, list):
        for child in value:
            normalize_timestamps(child)


def normalize_workspace_paths(value: Any, workspace_root: Path) -> Any:
    """Replace only the current checkout prefix in CycloneDX strings."""

    if isinstance(value, dict):
        for key, child in value.items():
            value[key] = normalize_workspace_paths(child, workspace_root)
        return value
    if isinstance(value, list):
        for index, child in enumerate(value):
            value[index] = normalize_workspace_paths(child, workspace_root)
        return value
    if isinstance(value, str):
        root = workspace_root.resolve()
        return value.replace(root.as_uri(), "file:///workspace").replace(
            root.as_posix(), "/workspace"
        )
    return value


def normalize(path: Path, workspace_root: Path = ROOT) -> str:
    document = json.loads(path.read_text(encoding="utf-8"))
    document.pop("annotations", None)
    normalize_workspace_paths(document, workspace_root)
    normalize_timestamps(document)
    components = document.get("components", [])
    if isinstance(components, list):
        components.sort(key=component_key)
    dependencies = document.get("dependencies", [])
    if isinstance(dependencies, list):
        for dependency in dependencies:
            if isinstance(dependency, dict) and isinstance(dependency.get("dependsOn"), list):
                dependency["dependsOn"].sort()
        dependencies.sort(key=lambda dependency: str(dependency.get("ref", "")))

    identity = json.dumps(
        [
            {
                "purl": component.get("purl"),
                "name": component.get("name"),
                "version": component.get("version"),
            }
            for component in components
            if isinstance(component, dict)
        ],
        separators=(",", ":"),
        sort_keys=True,
    )
    seed = hashlib.sha256(identity.encode()).hexdigest()
    document["serialNumber"] = (
        f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, f'wp-01:{path.name}:{seed}')}"
    )
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sbom", type=Path, nargs="+")
    parser.add_argument("--workspace-root", type=Path, default=ROOT)
    args = parser.parse_args()
    for path in args.sbom:
        print(f"sha256:{normalize(path, args.workspace_root)}  {path}")
    print(f"PASS: normalized {len(args.sbom)} CycloneDX SBOM(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
