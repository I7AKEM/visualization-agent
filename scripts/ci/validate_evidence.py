#!/usr/bin/env python3
"""Validate work-package evidence schemas and their immutable Git relationships."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
HANDOFF_SCHEMA = ROOT / "schemas" / "handoff-v1.schema.json"
ACCEPTANCE_SCHEMA = ROOT / "schemas" / "integration-acceptance-v1.schema.json"
NORMATIVE_FILES = (
    "docs/production-spec/README.md",
    "docs/production-spec/01_DECISIONS_AND_ARCHITECTURE.md",
    "docs/production-spec/02_CONTRACTS_AND_STATE_MACHINES.md",
    "docs/production-spec/03_TEST_AND_FAILURE_MATRIX.md",
    "docs/production-spec/04_AGENT_EVAL_SPEC.md",
    "docs/production-spec/05_SECURITY_OPERATIONS_AND_DELIVERY.md",
    "docs/production-spec/06_TASK_DISPATCH_BRIEFS.md",
)
LOCAL_RUNTIME_SUBGATES = (
    "frozen_lock_start_health_shutdown",
    "offline_agent_api_and_stream",
    "wp_05_plus_real_ui",
    "later_package_suite_extension",
)
RUNTIME_EVIDENCE_REFERENCE = re.compile(
    r"^(?P<location>docs/evidence/wp-[0-9]{2}/[^#]+|github-actions://[^#]+)"
    r"#sha256:(?P<sha256>[0-9a-f]{64})$"
)


class EvidenceError(RuntimeError):
    """A deterministic evidence or Git invariant failed."""


def git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise EvidenceError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise EvidenceError(f"{path.relative_to(ROOT)} must contain a YAML mapping")
    return value


def load_schema(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(value)
    return value


def validate_document(path: Path, document: dict[str, Any], schema: dict[str, Any]) -> None:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.absolute_path))
    if errors:
        rendered = []
        for error in errors:
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            rendered.append(f"{location}: {error.message}")
        raise EvidenceError(f"{path.relative_to(ROOT)} schema errors:\n  " + "\n  ".join(rendered))


def assert_commit(commit: str, label: str) -> None:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise EvidenceError(f"{label} does not resolve to a Git commit: {commit}")


def assert_ancestor(ancestor: str, descendant: str, label: str) -> None:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise EvidenceError(f"{label}: {ancestor} is not an ancestor of {descendant}")


def work_package_from_path(path: Path) -> str:
    slug = path.parent.name
    if not slug.startswith("wp-"):
        raise EvidenceError(f"unexpected handoff directory: {path.relative_to(ROOT)}")
    return slug.upper()


def known_requirement_ids() -> set[str]:
    result: set[str] = set()
    governance = ROOT / "docs" / "governance" / "requirements-traceability.yaml"
    if governance.exists():
        data = load_yaml(governance)
        result.update(
            row["id"]
            for row in data.get("requirements", [])
            if isinstance(row, dict) and "id" in row
        )
    registry = ROOT / "tests" / "requirements.yaml"
    if registry.exists():
        data = load_yaml(registry)
        result.update(
            row["id"]
            for row in data.get("requirements", [])
            if isinstance(row, dict) and "id" in row
        )
    return result


def validate_handoff(
    path: Path,
    handoff: dict[str, Any],
    acceptance_by_wp: dict[str, tuple[Path, dict[str, Any]]],
    requirements: set[str],
) -> None:
    wp = handoff["work_package"]
    validate_local_runtime_handoff(handoff)
    if work_package_from_path(path) != wp:
        raise EvidenceError(f"{path.relative_to(ROOT)} path does not match work_package {wp}")

    self_path = path.relative_to(ROOT).as_posix()
    if self_path in handoff["changed_paths"]:
        raise EvidenceError(f"{self_path} must not list itself in changed_paths")
    unknown_requirements = sorted(set(handoff["requirements"]) - requirements)
    if unknown_requirements:
        raise EvidenceError(f"{self_path} cites unknown requirement IDs: {unknown_requirements}")

    base = handoff["base_integration_commit"]
    delivery = handoff["delivery_commit"]
    assert_commit(base, f"{wp} base_integration_commit")
    assert_commit(delivery, f"{wp} delivery_commit")
    assert_ancestor(base, delivery, f"{wp} delivery ancestry")

    actual_paths = git("diff", "--name-only", base, delivery).splitlines()
    if actual_paths != handoff["changed_paths"]:
        raise EvidenceError(
            f"{wp} changed_paths mismatch; recorded={handoff['changed_paths']!r}, "
            f"actual={actual_paths!r}"
        )

    handoff_commit = handoff["handoff_commit"]
    state = handoff["handoff_state"]
    if state == "submitted":
        if wp in acceptance_by_wp:
            raise EvidenceError(
                f"{wp} is submitted but already has an integration acceptance record"
            )
        return

    assert_commit(handoff_commit, f"{wp} handoff_commit")
    parent = git("rev-parse", f"{handoff_commit}^")
    if parent != delivery:
        raise EvidenceError(
            f"{wp} handoff commit parent {parent} does not equal delivery {delivery}"
        )
    metadata_paths = git("diff", "--name-only", delivery, handoff_commit).splitlines()
    if metadata_paths != [self_path]:
        raise EvidenceError(
            f"{wp} handoff commit must change only {self_path}; got {metadata_paths!r}"
        )
    if wp not in acceptance_by_wp:
        raise EvidenceError(f"{wp} state {state!r} requires an integration acceptance record")


def validate_runtime_evidence_references(wp: str, references: Any) -> None:
    if not isinstance(references, list) or not references:
        raise EvidenceError(f"{wp} LOCAL-RUNTIME requires checksummed evidence references")
    for reference in references:
        match = (
            RUNTIME_EVIDENCE_REFERENCE.fullmatch(reference) if isinstance(reference, str) else None
        )
        if match is None:
            raise EvidenceError(f"{wp} LOCAL-RUNTIME evidence reference is invalid: {reference!r}")
        location = match.group("location")
        if location.startswith("github-actions://"):
            continue
        path = (ROOT / location).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise EvidenceError(f"{wp} LOCAL-RUNTIME evidence file does not exist: {location}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != match.group("sha256"):
            raise EvidenceError(
                f"{wp} LOCAL-RUNTIME evidence checksum mismatch for {location}: "
                f"recorded={match.group('sha256')} actual={actual}"
            )


def validate_local_runtime_handoff(handoff: dict[str, Any]) -> None:
    """Fail closed on submitted or accepted WP-01+ runtime handoff evidence."""

    wp = handoff["work_package"]
    if wp == "WP-00":
        return
    gate = handoff.get("local_runtime_evidence")
    if not isinstance(gate, dict):
        raise EvidenceError(f"{wp} handoff lacks local_runtime_evidence")
    active = handoff["handoff_state"] in {"submitted", "accepted", "conditionally_accepted"}
    status = gate.get("status")
    if active and status == "failed":
        raise EvidenceError(f"{wp} active handoff has failed LOCAL-RUNTIME gate")
    subgates = gate.get("subgates")
    if not isinstance(subgates, dict):
        raise EvidenceError(f"{wp} handoff LOCAL-RUNTIME subgates must be a mapping")
    for name in LOCAL_RUNTIME_SUBGATES:
        status_value = subgates.get(name)
        if status_value not in {"passed", "failed", "not_applicable"}:
            raise EvidenceError(f"{wp} handoff LOCAL-RUNTIME subgate {name} is missing or invalid")
        if active and status_value == "failed":
            raise EvidenceError(f"{wp} active handoff has failed LOCAL-RUNTIME subgate {name}")
        if status_value == "not_applicable":
            assert_exact_not_applicable_rationale(wp, name, gate.get("rationale"))
    if wp == "WP-01" and active:
        if status != "passed":
            raise EvidenceError("WP-01 owns a runnable web shell; LOCAL-RUNTIME must pass")
        if subgates.get("frozen_lock_start_health_shutdown") != "passed":
            raise EvidenceError("WP-01 owned frozen-lock start/health/shutdown subgate must pass")
    validate_runtime_evidence_references(wp, gate.get("dataset_result_artifact_hashes"))


def validate_local_runtime_acceptance(acceptance: dict[str, Any]) -> None:
    """Reject accepted WP-01+ evidence with failed or unjustified runtime gates."""

    wp = acceptance["work_package"]
    if wp == "WP-00":
        return
    gate = acceptance.get("local_runtime_gate")
    if not isinstance(gate, dict):
        raise EvidenceError(f"{wp} acceptance lacks local_runtime_gate")

    accepted = acceptance["status"] in {"accepted", "conditionally_accepted"}
    status = gate.get("status")
    if accepted and status == "failed":
        raise EvidenceError(f"{wp} accepted record has failed LOCAL-RUNTIME gate")
    if accepted and status not in {"passed", "not_applicable"}:
        raise EvidenceError(f"{wp} accepted record has missing or invalid LOCAL-RUNTIME gate")

    components = gate.get("components")
    if accepted and (not isinstance(components, list) or not components):
        raise EvidenceError(f"{wp} accepted LOCAL-RUNTIME gate must name owned components")

    subgates = gate.get("subgates")
    if not isinstance(subgates, dict):
        raise EvidenceError(f"{wp} local_runtime_gate.subgates must be a mapping")
    for name in LOCAL_RUNTIME_SUBGATES:
        record = subgates.get(name)
        if not isinstance(record, dict):
            raise EvidenceError(f"{wp} LOCAL-RUNTIME subgate {name} is missing or invalid")
        status = record.get("status")
        if accepted and status == "failed":
            raise EvidenceError(f"{wp} accepted record has failed LOCAL-RUNTIME subgate {name}")
        if status == "not_applicable":
            assert_exact_not_applicable_rationale(wp, name, record.get("rationale"))
    if wp == "WP-01" and accepted:
        if gate.get("status") != "passed":
            raise EvidenceError("WP-01 owns a runnable web shell; LOCAL-RUNTIME must pass")
        if subgates["frozen_lock_start_health_shutdown"].get("status") != "passed":
            raise EvidenceError("WP-01 owned frozen-lock start/health/shutdown subgate must pass")
    if gate.get("status") == "not_applicable":
        assert_exact_not_applicable_rationale(wp, "overall gate", gate.get("rationale"))
    if accepted:
        runtime_rows = [
            row
            for row in acceptance.get("validation", [])
            if isinstance(row, dict) and row.get("id") == "LOCAL-RUNTIME"
        ]
        if not runtime_rows or any(
            row.get("exit_code") != 0
            or not str(row.get("result", "")).strip().lower().startswith("pass")
            for row in runtime_rows
        ):
            raise EvidenceError(f"{wp} accepted record lacks a passing LOCAL-RUNTIME validation")
        validate_runtime_evidence_references(wp, gate.get("evidence"))


def assert_exact_not_applicable_rationale(wp: str, label: str, rationale: Any) -> None:
    if not isinstance(rationale, str):
        raise EvidenceError(f"{wp} LOCAL-RUNTIME {label} lacks a rationale")
    normalized = " ".join(rationale.lower().split())
    ownership_markers = ("wp-", "own", "depend", "runnable", "documentation")
    if len(normalized) < 40 or not any(marker in normalized for marker in ownership_markers):
        raise EvidenceError(
            f"{wp} LOCAL-RUNTIME {label} not_applicable rationale must name exact "
            "ownership or dependency grounds"
        )


def validate_acceptance(
    path: Path,
    acceptance: dict[str, Any],
    handoff_by_wp: dict[str, tuple[Path, dict[str, Any]]],
) -> None:
    wp = acceptance["work_package"]
    validate_local_runtime_acceptance(acceptance)
    expected_name = f"{wp.lower()}-acceptance.yaml"
    if path.name != expected_name:
        raise EvidenceError(f"{path.relative_to(ROOT)} must be named {expected_name}")
    if wp not in handoff_by_wp:
        raise EvidenceError(f"{wp} acceptance has no matching handoff")

    _, handoff = handoff_by_wp[wp]
    for anchor in ("delivery_commit", "handoff_commit"):
        if acceptance[anchor] != handoff[anchor]:
            raise EvidenceError(f"{wp} acceptance {anchor} does not match handoff")
    if acceptance["status"] != handoff["handoff_state"]:
        raise EvidenceError(f"{wp} acceptance status does not match handoff_state")

    for anchor in (
        "acceptance_base_commit",
        "delivery_commit",
        "handoff_commit",
        "specification_commit",
    ):
        assert_commit(acceptance[anchor], f"{wp} {anchor}")
    assert_ancestor(
        acceptance["handoff_commit"], acceptance["acceptance_base_commit"], f"{wp} acceptance base"
    )

    introductions = git(
        "log", "--diff-filter=A", "--format=%H", "--", path.relative_to(ROOT).as_posix()
    ).splitlines()
    if len(introductions) != 1:
        raise EvidenceError(
            f"{wp} acceptance must have exactly one introduction commit; got {introductions!r}"
        )
    introduction = introductions[0]
    parent = git("rev-parse", f"{introduction}^")
    if parent != acceptance["acceptance_base_commit"]:
        raise EvidenceError(
            f"{wp} acceptance introduction parent {parent} does not equal acceptance_base_commit "
            f"{acceptance['acceptance_base_commit']}"
        )
    assert_ancestor(introduction, "HEAD", f"{wp} acceptance introduction")

    specification = acceptance["specification_commit"]
    for normative_path in NORMATIVE_FILES:
        result = subprocess.run(
            ["git", "cat-file", "-e", f"{specification}:{normative_path}"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise EvidenceError(f"{wp} specification_commit lacks {normative_path}")

    if acceptance.get("production_approved") is True and acceptance["unresolved_owner_inputs"]:
        raise EvidenceError(f"{wp} cannot claim production approval with unresolved owner inputs")
    failed_results = [
        row["id"]
        for row in acceptance["validation"]
        if isinstance(row, dict) and row.get("exit_code", 0) != 0
    ]
    if acceptance["status"] in {"accepted", "conditionally_accepted"} and failed_results:
        raise EvidenceError(f"{wp} accepted record contains failed validations: {failed_results}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-git", action="store_true", help="Validate schema only")
    args = parser.parse_args()

    handoff_schema = load_schema(HANDOFF_SCHEMA)
    acceptance_schema = load_schema(ACCEPTANCE_SCHEMA)
    handoff_paths = sorted(ROOT.glob("docs/evidence/wp-*/handoff.yaml"))
    acceptance_paths = sorted(ROOT.glob("docs/evidence/integration/wp-*-acceptance.yaml"))
    if not handoff_paths:
        raise EvidenceError("no work-package handoff files found")

    handoffs: dict[str, tuple[Path, dict[str, Any]]] = {}
    acceptances: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in handoff_paths:
        document = load_yaml(path)
        validate_document(path, document, handoff_schema)
        validate_local_runtime_handoff(document)
        wp = document["work_package"]
        if wp in handoffs:
            raise EvidenceError(f"duplicate handoff for {wp}")
        handoffs[wp] = (path, document)
    for path in acceptance_paths:
        document = load_yaml(path)
        validate_document(path, document, acceptance_schema)
        validate_local_runtime_acceptance(document)
        wp = document["work_package"]
        if wp in acceptances:
            raise EvidenceError(f"duplicate acceptance for {wp}")
        acceptances[wp] = (path, document)

    if not args.skip_git:
        requirements = known_requirement_ids()
        for path, handoff in handoffs.values():
            validate_handoff(path, handoff, acceptances, requirements)
        for path, acceptance in acceptances.values():
            validate_acceptance(path, acceptance, handoffs)

    print(
        f"PASS: validated {len(handoffs)} handoff(s), {len(acceptances)} acceptance record(s), "
        "both JSON Schemas, and Git relationships"
        + (" (Git checks skipped)" if args.skip_git else "")
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvidenceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
