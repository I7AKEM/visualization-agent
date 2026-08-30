#!/usr/bin/env python3
"""Fail closed when Trivy license evidence is empty, partial, or denied."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DENIED = re.compile(r"(?i)\b(?:A?GPL-(?:1[.]0|2[.]0|3[.]0)|SSPL-1[.]0)\b")
ALLOWED_SEVERITIES = {"UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL"}
NODE_SENTINELS = {"@cyclonedx/cdxgen", "next", "react"}
PYTHON_SENTINELS = {"cyclonedx-bom", "fastapi", "pydantic-ai-slim"}


class TrivyValidationError(ValueError):
    """The Trivy report cannot support the WP-01 license gate."""


def require_string(row: dict[str, Any], key: str, index: int) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TrivyValidationError(f"license row {index} has no non-empty {key}")
    return value


def validate(document: dict[str, Any]) -> tuple[int, int, int]:
    if document.get("SchemaVersion") != 2:
        raise TrivyValidationError("Trivy JSON must use SchemaVersion 2")
    results = document.get("Results")
    if not isinstance(results, list) or not results:
        raise TrivyValidationError("Trivy JSON contains no Results")

    rows: list[dict[str, Any]] = []
    for result_index, result in enumerate(results):
        if not isinstance(result, dict):
            raise TrivyValidationError(f"Trivy Result {result_index} is not an object")
        licenses = result.get("Licenses", [])
        if not isinstance(licenses, list):
            raise TrivyValidationError(f"Trivy Result {result_index} Licenses is not a list")
        for row in licenses:
            if not isinstance(row, dict):
                raise TrivyValidationError("Trivy license row is not an object")
            rows.append(row)

    if not rows:
        raise TrivyValidationError("Trivy reported zero license records")

    node_packages: set[str] = set()
    python_packages: set[str] = set()
    denied: list[str] = []
    for index, row in enumerate(rows):
        name = require_string(row, "Name", index)
        package = require_string(row, "PkgName", index)
        severity = require_string(row, "Severity", index)
        file_path = require_string(row, "FilePath", index)
        if severity not in ALLOWED_SEVERITIES:
            raise TrivyValidationError(f"license row {index} has invalid Severity {severity!r}")
        if file_path.startswith("node_modules/"):
            node_packages.add(package)
        if file_path.startswith(".venv/") and ".dist-info/METADATA" in file_path:
            python_packages.add(package)
        if DENIED.search(name):
            denied.append(f"{package}: {name}")

    missing_node = sorted(NODE_SENTINELS - node_packages)
    missing_python = sorted(PYTHON_SENTINELS - python_packages)
    if missing_node:
        raise TrivyValidationError(
            f"Trivy Node license evidence is partial; missing sentinels: {missing_node}"
        )
    if missing_python:
        raise TrivyValidationError(
            f"Trivy Python license evidence is partial; missing sentinels: {missing_python}"
        )
    if denied:
        raise TrivyValidationError(
            "Trivy found provisionally denied licenses: " + ", ".join(sorted(set(denied)))
        )
    return len(rows), len(node_packages), len(python_packages)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    try:
        document = json.loads(args.report.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise TrivyValidationError("Trivy JSON root must be an object")
        license_count, node_count, python_count = validate(document)
    except (OSError, json.JSONDecodeError, TrivyValidationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        f"PASS: Trivy reported {license_count} license record(s) covering "
        f"{node_count} Node and {python_count} Python package(s); all required sentinels "
        "are present and the AGPL/GPL/SSPL deny policy passed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
