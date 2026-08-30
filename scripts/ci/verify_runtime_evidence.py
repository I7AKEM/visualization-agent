#!/usr/bin/env python3
"""Verify committed WP-01 LOCAL-RUNTIME artifacts and their checksum binding."""

from __future__ import annotations

import argparse
import hashlib
import json
import signal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_FILES = {
    "asset-headers.txt",
    "client-asset.js",
    "failure-retest.yaml",
    "page-body.html",
    "page-headers.txt",
    "startup-shutdown.log",
    "trace.json",
}


class RuntimeEvidenceError(RuntimeError):
    """A durable runtime artifact or semantic assertion is invalid."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checksum_manifest(path: Path) -> dict[str, str]:
    records: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        digest, separator, name = line.partition("  ")
        if not separator or len(digest) != 64 or name in records:
            raise RuntimeEvidenceError(f"invalid checksum manifest line: {line!r}")
        records[name] = digest
    return records


def verify(directory: Path) -> dict[str, Any]:
    directory = directory.resolve()
    actual_files = {
        path.name
        for path in directory.iterdir()
        if path.is_file() and path.name != "checksums.sha256"
    }
    if actual_files != REQUIRED_FILES:
        raise RuntimeEvidenceError(
            f"runtime evidence file set mismatch: expected={sorted(REQUIRED_FILES)} "
            f"actual={sorted(actual_files)}"
        )
    checksums = checksum_manifest(directory / "checksums.sha256")
    if set(checksums) != REQUIRED_FILES:
        raise RuntimeEvidenceError(
            "checksum manifest does not bind the complete runtime evidence set"
        )
    for name, expected in checksums.items():
        actual = sha256(directory / name)
        if actual != expected:
            raise RuntimeEvidenceError(
                f"runtime evidence checksum mismatch for {name}: "
                f"expected={expected} actual={actual}"
            )

    trace = json.loads((directory / "trace.json").read_text(encoding="utf-8"))
    page = trace.get("page", {})
    asset = trace.get("asset", {})
    shutdown = trace.get("shutdown", {})
    assertions = {
        "result": trace.get("result") == "passed",
        "startup_error": trace.get("startup_error") is None,
        "page_status": page.get("status") == "HTTP/1.1 200 OK",
        "page_assertion": page.get("body_assertion_passed") is True,
        "page_hash": page.get("sha256") == sha256(directory / "page-body.html"),
        "asset_status": asset.get("status") == "HTTP/1.1 200 OK",
        "asset_hash": asset.get("sha256") == sha256(directory / "client-asset.js"),
        "shutdown_error": shutdown.get("error") is None,
        "forced_kill": shutdown.get("forced_kill") is False,
        "exit_code": shutdown.get("process_exit_code") in {130, -signal.SIGINT},
        "listener": shutdown.get("listener_remaining") is False,
    }
    failures = sorted(name for name, passed in assertions.items() if not passed)
    if failures:
        raise RuntimeEvidenceError(f"runtime evidence semantic assertions failed: {failures}")
    return trace


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "directory",
        type=Path,
        nargs="?",
        default=ROOT / "docs" / "evidence" / "wp-01" / "runtime",
    )
    args = parser.parse_args()
    trace = verify(args.directory)
    print(
        "PASS: committed LOCAL-RUNTIME artifacts are complete, checksummed, and semantic; "
        f"page={trace['page']['status']} asset={trace['asset']['status']} "
        f"shutdown={trace['shutdown']['process_exit_code']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeEvidenceError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1) from exc
