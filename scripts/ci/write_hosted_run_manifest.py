#!/usr/bin/env python3
"""Write machine-readable GitHub run identity for later integration acceptance."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path


def required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"missing hosted CI environment {name}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tested-sha", required=True)
    parser.add_argument("--artifact-reference", action="append", default=[])
    args = parser.parse_args()
    event_sha = required_environment("GITHUB_SHA")
    tested_sha = args.tested_sha.strip()
    run_id = required_environment("GITHUB_RUN_ID")
    run_attempt = required_environment("GITHUB_RUN_ATTEMPT")
    if not re.fullmatch(r"[0-9a-f]{40}", event_sha):
        raise SystemExit("GITHUB_SHA must be a 40-hex commit")
    if not re.fullmatch(r"[0-9a-f]{40}", tested_sha):
        raise SystemExit("--tested-sha must be a 40-hex commit")
    if not run_id.isdigit() or not run_attempt.isdigit():
        raise SystemExit("GitHub run ID and attempt must be numeric")
    server = required_environment("GITHUB_SERVER_URL").rstrip("/")
    repository = required_environment("GITHUB_REPOSITORY")
    checkout_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if checkout_sha != tested_sha:
        raise SystemExit(f"tested SHA {tested_sha} does not match checkout HEAD {checkout_sha}")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema_version": 1,
        "record_type": "hosted_ci_run_context",
        "gate": args.gate,
        "status": "required_jobs_passed_to_manifest_step",
        "exact_sha": tested_sha,
        "checkout_sha": checkout_sha,
        "event_sha": event_sha,
        "pull_request_head_sha": os.environ.get("WP01_PR_HEAD_SHA", "").strip() or None,
        "pull_request_base_sha": os.environ.get("WP01_PR_BASE_SHA", "").strip() or None,
        "event_name": required_environment("GITHUB_EVENT_NAME"),
        "workflow": required_environment("GITHUB_WORKFLOW"),
        "run_id": int(run_id),
        "run_attempt": int(run_attempt),
        "run_url": f"{server}/{repository}/actions/runs/{run_id}/attempts/{run_attempt}",
        "artifact_references": sorted(set(args.artifact_reference)),
        "acceptance_rule": (
            "Integration must independently verify the overall hosted run conclusion is success."
        ),
    }
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"PASS: wrote hosted run context for {args.gate} at exact SHA {tested_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
