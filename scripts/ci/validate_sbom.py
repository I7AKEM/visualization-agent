#!/usr/bin/env python3
"""Validate and checksum generated CycloneDX SBOM documents."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

FORBIDDEN_VERSIONS = {"", "*", "latest", "main", "master", "unknown"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("bomFormat") != "CycloneDX":
        raise ValueError("bomFormat must be CycloneDX")
    if document.get("specVersion") not in {"1.5", "1.6", 1.5, 1.6}:
        raise ValueError("specVersion must be CycloneDX 1.5 or 1.6")
    if not isinstance(document.get("serialNumber"), str) or not document["serialNumber"].startswith(
        "urn:uuid:"
    ):
        raise ValueError("serialNumber must be a CycloneDX UUID URN")
    components = document.get("components")
    if not isinstance(components, list) or not components:
        raise ValueError("components must be a non-empty array")
    references: set[str] = set()
    licensed = 0
    for index, component in enumerate(components):
        if not isinstance(component, dict):
            raise ValueError(f"components[{index}] is not an object")
        for required in ("type", "name", "version"):
            if not isinstance(component.get(required), str) or not component[required]:
                raise ValueError(f"components[{index}].{required} is required")
        if component["version"].lower() in FORBIDDEN_VERSIONS or "*" in component["version"]:
            raise ValueError(f"components[{index}] has mutable/unknown version")
        reference = component.get("bom-ref") or component.get("purl")
        if not isinstance(reference, str) or not reference:
            raise ValueError(f"components[{index}] needs bom-ref or purl")
        if reference in references:
            raise ValueError(f"duplicate component reference: {reference}")
        references.add(reference)
        if component.get("licenses"):
            licensed += 1
    return {
        "path": str(path),
        "sha256": sha256(path),
        "component_count": len(components),
        "components_with_license": licensed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sbom", type=Path, nargs="+")
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    summaries: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in args.sbom:
        try:
            summaries.append(validate(path))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{path}: {exc}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(
            json.dumps({"schema_version": 1, "sboms": summaries}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    for summary in summaries:
        print(
            f"sha256:{summary['sha256']}  {summary['path']} "
            f"({summary['component_count']} components, "
            f"{summary['components_with_license']} with licenses)"
        )
    print(f"PASS: validated {len(summaries)} CycloneDX SBOM(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
