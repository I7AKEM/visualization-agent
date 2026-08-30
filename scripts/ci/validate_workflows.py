#!/usr/bin/env python3
"""Static supply-chain policy for GitHub workflow sources."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
LOCK_PATH = ROOT / "infra" / "dev" / "ci-tools.lock.json"
USES = re.compile(r"^[ \t]*uses:[ \t]*([^#\s]+)", re.MULTILINE)
RUNNER = re.compile(r"^[ \t]*runs-on:[ \t]*([^#\s]+)", re.MULTILINE)
FORBIDDEN = {
    "pull_request_target": (
        "pull_request_target can execute untrusted PR code with write-capable context"
    ),
    "curl | sh": "pipe-to-shell installer",
    "curl | bash": "pipe-to-shell installer",
    "wget | sh": "pipe-to-shell installer",
    "wget | bash": "pipe-to-shell installer",
    "npm install -g": "global mutable Node installation",
    "corepack enable": "Corepack shim mutation outside the repository-local cache",
    "pip install --upgrade": "mutable Python bootstrap",
    "OPENAI_API_KEY": "external model credential reference",
    "ANTHROPIC_API_KEY": "external model credential reference",
    "GOOGLE_API_KEY": "external model credential reference",
}


def fail(errors: list[str]) -> None:
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    pinned_actions = {name: record["sha"] for name, record in lock["github_actions"].items()}
    workflow_paths = sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])
    if not workflow_paths:
        fail(["no GitHub workflows found"])

    errors: list[str] = []
    seen_actions: set[str] = set()
    for path in workflow_paths:
        relative = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")
        for marker, reason in FORBIDDEN.items():
            if marker in text:
                errors.append(f"{relative}: forbidden {reason}: {marker!r}")
        if not re.search(
            r"(?m)^permissions:\s*\n(?:[ \t]+[^\n]+\n)*?[ \t]+contents:[ \t]+read\s*$", text
        ):
            errors.append(f"{relative}: top-level permissions must include contents: read")
        for runner in RUNNER.findall(text):
            if runner == "ubuntu-latest" or runner.endswith("-latest"):
                errors.append(f"{relative}: floating runner label {runner!r} is forbidden")
            elif runner not in {"ubuntu-24.04"} and "${{" not in runner:
                errors.append(f"{relative}: unreviewed runner label {runner!r}")
        for reference in USES.findall(text):
            if reference.startswith("./"):
                continue
            if "@" not in reference:
                errors.append(f"{relative}: action has no immutable reference: {reference}")
                continue
            action, revision = reference.rsplit("@", 1)
            lock_name = next(
                (
                    name
                    for name in pinned_actions
                    if action == name or action.startswith(f"{name}/")
                ),
                None,
            )
            expected = pinned_actions.get(lock_name) if lock_name else None
            if expected is None:
                errors.append(
                    f"{relative}: action {action!r} is absent from {LOCK_PATH.relative_to(ROOT)}"
                )
            elif revision != expected:
                errors.append(
                    f"{relative}: {action} uses {revision}, expected locked SHA {expected}"
                )
            if not re.fullmatch(r"[0-9a-f]{40}", revision):
                errors.append(f"{relative}: {action} is not pinned to a 40-hex commit")
            if lock_name:
                seen_actions.add(lock_name)
        if re.search(r"(?m)^\s*(?:image:|container:)\s*[^\n]+:(?:latest|main|master)\s*$", text):
            errors.append(f"{relative}: floating container tag is forbidden")
        if "actions/setup-node" in text:
            if "COREPACK_HOME:" not in text:
                errors.append(f"{relative}: Node workflow lacks repository-scoped COREPACK_HOME")
            if "corepack pnpm" not in text:
                errors.append(
                    f"{relative}: Node workflow must invoke the pinned manager via corepack pnpm"
                )
            if 'NEXT_TELEMETRY_DISABLED: "1"' not in text:
                errors.append(f"{relative}: Node workflow must disable Next telemetry")
        if "scripts/ci/write_hosted_run_manifest.py" in text:
            required_identity_markers = (
                "WP01_TESTED_SHA:",
                "--tested-sha",
                "ref: ${{ env.WP01_TESTED_SHA }}",
            )
            missing = [marker for marker in required_identity_markers if marker not in text]
            if missing:
                errors.append(
                    f"{relative}: hosted evidence lacks exact checked-out SHA markers: {missing}"
                )

    unused = sorted(set(pinned_actions) - seen_actions)
    if unused:
        errors.append(f"{LOCK_PATH.relative_to(ROOT)} contains unused action pins: {unused}")
    if errors:
        fail(errors)
    print(
        f"PASS: {len(workflow_paths)} workflow(s), {len(seen_actions)} immutable action pin(s), "
        "fixed runners"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
