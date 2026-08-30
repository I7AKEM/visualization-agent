#!/usr/bin/env python3
"""Conservative, deterministic repository secret scanner with redacted findings."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAX_FILE_BYTES = 5 * 1024 * 1024
PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "aws-access-key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "github-token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,255}\b"),
    "github-fine-grained-token": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{50,255}\b"),
    "openai-token": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,255}\b"),
    "anthropic-token": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{24,255}\b"),
    "slack-token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,255}\b"),
    "generic-secret-assignment": re.compile(
        r"(?i)\b(?:api[_-]?key|client[_-]?secret|password|passwd|access[_-]?token)\b"
        r"\s*[:=]\s*['\"]([A-Za-z0-9+/_.=-]{20,})['\"]"
    ),
}
PLACEHOLDERS = re.compile(
    r"(?i)^(?:example|placeholder|dummy|fake|test|redacted|changeme|none|null|x+)$"
)
BINARY_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".pdf",
    ".ttf",
    ".woff",
    ".woff2",
    ".zip",
    ".gz",
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / raw.decode("utf-8") for raw in result.stdout.split(b"\0") if raw]


def scan_text(label: str, text: str) -> list[str]:
    findings: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for pattern_name, pattern in PATTERNS.items():
            match = pattern.search(line)
            if not match:
                continue
            if pattern_name == "generic-secret-assignment" and PLACEHOLDERS.fullmatch(
                match.group(1)
            ):
                continue
            findings.append(f"{label}:{line_number}: possible {pattern_name} (value redacted)")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--history", action="store_true", help="also scan textual Git patch history"
    )
    args = parser.parse_args()
    findings: list[str] = []
    scanned = 0
    for path in tracked_files():
        if (
            not path.is_file()
            or path.suffix.lower() in BINARY_SUFFIXES
            or path.stat().st_size > MAX_FILE_BYTES
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        scanned += 1
        findings.extend(scan_text(path.relative_to(ROOT).as_posix(), text))

    if args.history:
        result = subprocess.run(
            ["git", "log", "--all", "--no-ext-diff", "--no-textconv", "-p", "--format=commit:%H"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            errors="replace",
        )
        findings.extend(scan_text("<git-history>", result.stdout))

    if findings:
        for finding in findings:
            print(f"ERROR: {finding}", file=sys.stderr)
        return 1
    print(
        f"PASS: scanned {scanned} repository text file(s)"
        + (" and Git patch history" if args.history else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
