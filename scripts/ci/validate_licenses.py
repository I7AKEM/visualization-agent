#!/usr/bin/env python3
"""Fail on missing or provisionally denied licenses in generated SBOMs."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import yaml
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[2]
DENIED = re.compile(r"(?i)\b(?:A?GPL-(?:1[.]0|2[.]0|3[.]0)|SSPL-1[.]0)\b")
FIRST_PARTY_PREFIXES = ("@visualization-agent/", "visualization-agent")
NODE_EVIDENCE = ROOT / "docs" / "evidence" / "wp-01" / "node-dependencies.yaml"
PYTHON_EVIDENCE = ROOT / "docs" / "evidence" / "wp-01" / "python-dependencies.yaml"
NON_ENVIRONMENT_DIRECT = {("hatchling", "1.32.0")}
EXCLUDED_PARTS = {".git", ".next", ".venv", "agent", "artifacts", "docs", "node_modules"}


def license_values(component: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for entry in component.get("licenses", []):
        if not isinstance(entry, dict):
            continue
        if isinstance(entry.get("expression"), str):
            values.append(entry["expression"])
        license_record = entry.get("license")
        if isinstance(license_record, dict):
            for key in ("id", "name"):
                if isinstance(license_record.get(key), str):
                    values.append(license_record[key])
    return values


def component_name(component: dict[str, Any]) -> str:
    purl = component.get("purl")
    if isinstance(purl, str) and purl.startswith("pkg:") and "@" in purl:
        package_path = purl.split("/", 1)[1].rsplit("@", 1)[0]
        return unquote(package_path).lower()
    group = str(component.get("group", ""))
    name = str(component.get("name", ""))
    return (f"{group}/{name}" if group else name).lower()


def evidence_licenses() -> dict[tuple[str, str], str]:
    node = yaml.safe_load(NODE_EVIDENCE.read_text(encoding="utf-8"))
    python = yaml.safe_load(PYTHON_EVIDENCE.read_text(encoding="utf-8"))
    records: dict[tuple[str, str], str] = {}
    for entry in node["production_dependencies"]:
        records[(str(entry["package"]), str(entry["version"]))] = str(entry["license"])
    for name, entry in node["tooling"].items():
        records[(str(name), str(entry["version"]))] = str(entry["license"])
    for section in ("production_dependencies", "test_security_dependencies"):
        for entry in python[section]:
            records[(str(entry["package"]), str(entry["version"]))] = str(entry["license"])
    return records


def declared_direct_dependencies() -> set[tuple[str, str]]:
    direct: set[tuple[str, str]] = set()
    for path in ROOT.rglob("package.json"):
        if any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts):
            continue
        manifest = json.loads(path.read_text(encoding="utf-8"))
        for group in ("dependencies", "devDependencies", "optionalDependencies"):
            for name, version in manifest.get(group, {}).items():
                if isinstance(version, str) and not version.startswith("workspace:"):
                    direct.add((str(name).lower(), version))

    for path in ROOT.rglob("pyproject.toml"):
        if any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts):
            continue
        manifest = tomllib.loads(path.read_text(encoding="utf-8"))
        requirements: list[str] = list(manifest.get("project", {}).get("dependencies", []))
        for values in manifest.get("dependency-groups", {}).values():
            requirements.extend(value for value in values if isinstance(value, str))
        requirements.extend(manifest.get("build-system", {}).get("requires", []))
        for raw_requirement in requirements:
            requirement = Requirement(raw_requirement)
            exact_versions = [
                specifier.version
                for specifier in requirement.specifier
                if specifier.operator == "=="
            ]
            if len(exact_versions) != 1:
                raise ValueError(f"non-exact Python declaration in {path}: {raw_requirement}")
            direct.add((requirement.name.lower().replace("_", "-"), exact_versions[0]))
    return direct


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sbom", type=Path, nargs="+")
    args = parser.parse_args()
    missing: list[str] = []
    denied: list[str] = []
    reviewed = 0
    generator_metadata_gaps = 0
    evidence = evidence_licenses()
    declared = declared_direct_dependencies()
    unrecorded_direct = sorted(declared - set(evidence))
    if unrecorded_direct:
        for name, version in unrecorded_direct:
            print(
                f"ERROR: direct dependency absent from exact license evidence: {name}@{version}",
                file=sys.stderr,
            )
        return 1
    seen_direct: set[tuple[str, str]] = set()
    for path in args.sbom:
        document = json.loads(path.read_text(encoding="utf-8"))
        for component in document.get("components", []):
            name = component_name(component)
            version = str(component.get("version", "<unversioned>"))
            licenses = license_values(component)
            key = (name, version)
            recorded_license = evidence.get(key)
            if recorded_license:
                seen_direct.add(key)
                licenses = [*licenses, recorded_license]
            if not licenses:
                if not name.startswith(FIRST_PARTY_PREFIXES):
                    generator_metadata_gaps += 1
                continue
            reviewed += 1
            for license_value in licenses:
                if DENIED.search(license_value):
                    denied.append(f"{name}@{version}: {license_value}")
    missing.extend(
        f"{name}@{version}"
        for name, version in sorted(set(evidence) - seen_direct - NON_ENVIRONMENT_DIRECT)
    )
    for value in sorted(set(missing)):
        print(f"ERROR: missing license metadata: {value}", file=sys.stderr)
    for value in sorted(set(denied)):
        print(f"ERROR: provisionally denied license: {value}", file=sys.stderr)
    if missing or denied:
        return 1
    print(
        f"PASS: reviewed license metadata for {reviewed} SBOM component(s), including all "
        f"{len(declared)} declared direct dependencies and {len(evidence)} reviewed exact records; "
        "SBOM generators omitted metadata for "
        f"{generator_metadata_gaps} transitive/platform components covered by dependency review"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
