from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

CI_DIR = Path(__file__).resolve().parents[1]
ROOT = CI_DIR.parents[1]
sys.path.insert(0, str(CI_DIR))

import build_foundation_artifact  # noqa: E402
import normalize_sbom  # noqa: E402
import rebuild_foundation  # noqa: E402
import scan_secrets  # noqa: E402
import validate_evidence  # noqa: E402
import validate_trivy  # noqa: E402
import validate_workflows  # noqa: E402
import verify_lockfiles  # noqa: E402
import verify_runtime_evidence  # noqa: E402


def evidence_reference(path: str = "docs/evidence/wp-01/runtime-smoke.yaml") -> str:
    digest = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    return f"{path}#sha256:{digest}"


def schema(name: str) -> dict[str, object]:
    return json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))


def valid_handoff() -> dict[str, object]:
    return {
        "schema_version": 1,
        "work_package": "WP-01",
        "base_integration_commit": "a" * 40,
        "delivery_commit": "b" * 40,
        "handoff_commit": None,
        "handoff_state": "submitted",
        "changed_paths": ["scripts/ci/example.py"],
        "requirements": ["GOV-013"],
        "dependency_commits": {},
        "commands_run": [{"command": "pytest", "exit_code": 0, "result": "pass"}],
        "tests_not_run": [],
        "eval_manifest_versions": [],
        "migrations": [],
        "configuration_keys": [],
        "secret_names": [],
        "telemetry_changes": [],
        "disabled_features": ["DF-001"],
        "known_risks": [],
        "rollback_steps": ["revert delivery"],
        "critical_gates_passed": ["SCHEMA"],
        "reviewers_required": ["integration_owner"],
        "local_runtime_evidence": {
            "status": "passed",
            "rationale": (
                "WP-01 owns the web shell; WP-03, WP-05, WP-06, WP-08, WP-09, and WP-12 "
                "own the deferred API, agent, browser, renderer, map, and export dependencies."
            ),
            "subgates": {
                "frozen_lock_start_health_shutdown": "passed",
                "offline_agent_api_and_stream": "not_applicable",
                "wp_05_plus_real_ui": "not_applicable",
                "later_package_suite_extension": "not_applicable",
            },
            "frozen_lock_start_commands": ["start local shell"],
            "health_readiness_checks": ["HTTP 200"],
            "graceful_shutdown_checks": ["SIGINT; no listener remained"],
            "agent_api_stream_traces": [],
            "ui_e2e_artifacts": [],
            "dataset_result_artifact_hashes": [evidence_reference()],
            "failures_and_retests": ["Asset 404 was corrected and the retest passed."],
        },
    }


def valid_acceptance() -> dict[str, object]:
    rationale = "WP-01 owns only the runnable web foundation at this dependency stage."
    return {
        "schema_version": 1,
        "record_type": "integration_acceptance",
        "work_package": "WP-01",
        "status": "accepted",
        "acceptance_base_commit": "a" * 40,
        "delivery_commit": "b" * 40,
        "handoff_commit": "c" * 40,
        "specification_commit": "d" * 40,
        "acceptance_scope": {"foundation": True},
        "validation": [{"id": "LOCAL-RUNTIME", "result": "passed", "exit_code": 0}],
        "unresolved_owner_inputs": [],
        "disabled_features": ["DF-001"],
        "conditions": [],
        "rollback_steps": ["revert acceptance"],
        "dependent_task_base_rule": "acceptance_record_introduction_commit",
        "local_runtime_gate": {
            "status": "passed",
            "rationale": rationale,
            "components": ["web"],
            "subgates": {
                "frozen_lock_start_health_shutdown": {
                    "status": "passed",
                    "rationale": (
                        "WP-01 owns the web shell and its start and shutdown paths passed."
                    ),
                },
                "offline_agent_api_and_stream": {
                    "status": "not_applicable",
                    "rationale": (
                        "WP-03, WP-05, and WP-06 own the API, stream, and agent dependencies."
                    ),
                },
                "wp_05_plus_real_ui": {
                    "status": "not_applicable",
                    "rationale": (
                        "WP-05 owns the first real interactive UI behavior and browser dependency."
                    ),
                },
                "later_package_suite_extension": {
                    "status": "not_applicable",
                    "rationale": "WP-08, WP-09, and WP-12 own the later runnable suite extensions.",
                },
            },
            "evidence": [evidence_reference()],
            "integration_commands": ["pnpm start"],
        },
    }


def test_handoff_schema_accepts_submitted_null_commit() -> None:
    Draft202012Validator(schema("handoff-v1.schema.json")).validate(valid_handoff())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("handoff_commit", "c" * 40),
        ("work_package", "WP-15"),
        ("changed_paths", ["../outside"]),
    ],
)
def test_handoff_schema_rejects_invalid_submission(field: str, value: object) -> None:
    document = valid_handoff()
    document[field] = value
    errors = list(Draft202012Validator(schema("handoff-v1.schema.json")).iter_errors(document))
    assert errors


def test_accepted_handoff_requires_commit() -> None:
    document = valid_handoff()
    document["handoff_state"] = "accepted"
    errors = list(Draft202012Validator(schema("handoff-v1.schema.json")).iter_errors(document))
    assert errors


def test_wp_01_handoff_requires_local_runtime_evidence() -> None:
    document = valid_handoff()
    del document["local_runtime_evidence"]
    errors = list(Draft202012Validator(schema("handoff-v1.schema.json")).iter_errors(document))
    assert errors


def test_submitted_wp_01_handoff_rejects_failed_runtime() -> None:
    document = valid_handoff()
    document["local_runtime_evidence"]["status"] = "failed"  # type: ignore[index]
    errors = list(Draft202012Validator(schema("handoff-v1.schema.json")).iter_errors(document))
    assert errors
    with pytest.raises(validate_evidence.EvidenceError, match="failed LOCAL-RUNTIME gate"):
        validate_evidence.validate_local_runtime_handoff(document)


def test_submitted_wp_01_handoff_requires_checksums() -> None:
    document = valid_handoff()
    document["local_runtime_evidence"]["dataset_result_artifact_hashes"] = []  # type: ignore[index]
    errors = list(Draft202012Validator(schema("handoff-v1.schema.json")).iter_errors(document))
    assert errors
    with pytest.raises(validate_evidence.EvidenceError, match="checksummed evidence"):
        validate_evidence.validate_local_runtime_handoff(document)


def test_wp_00_handoff_allows_pre_gate_record() -> None:
    document = valid_handoff()
    document["work_package"] = "WP-00"
    del document["local_runtime_evidence"]
    Draft202012Validator(schema("handoff-v1.schema.json")).validate(document)


def test_accepted_wp_01_rejects_failed_local_runtime_gate() -> None:
    document = valid_acceptance()
    document["local_runtime_gate"]["status"] = "failed"  # type: ignore[index]
    errors = list(
        Draft202012Validator(schema("integration-acceptance-v1.schema.json")).iter_errors(document)
    )
    assert errors
    with pytest.raises(validate_evidence.EvidenceError, match="failed LOCAL-RUNTIME gate"):
        validate_evidence.validate_local_runtime_acceptance(document)


def test_accepted_wp_01_rejects_failed_local_runtime_subgate() -> None:
    document = valid_acceptance()
    subgates = document["local_runtime_gate"]["subgates"]  # type: ignore[index]
    subgates["offline_agent_api_and_stream"]["status"] = "failed"  # type: ignore[index]
    errors = list(
        Draft202012Validator(schema("integration-acceptance-v1.schema.json")).iter_errors(document)
    )
    assert errors
    with pytest.raises(validate_evidence.EvidenceError, match="failed LOCAL-RUNTIME subgate"):
        validate_evidence.validate_local_runtime_acceptance(document)


def test_accepted_wp_01_rejects_missing_local_runtime_subgate() -> None:
    document = valid_acceptance()
    subgates = document["local_runtime_gate"]["subgates"]  # type: ignore[index]
    del subgates["offline_agent_api_and_stream"]  # type: ignore[attr-defined]
    errors = list(
        Draft202012Validator(schema("integration-acceptance-v1.schema.json")).iter_errors(document)
    )
    assert errors
    with pytest.raises(validate_evidence.EvidenceError, match="missing or invalid"):
        validate_evidence.validate_local_runtime_acceptance(document)


def test_valid_exact_not_applicable_local_runtime_rationales_pass() -> None:
    document = valid_acceptance()
    Draft202012Validator(schema("integration-acceptance-v1.schema.json")).validate(document)
    validate_evidence.validate_local_runtime_acceptance(document)


def test_accepted_wp_01_rejects_all_not_applicable_runtime() -> None:
    document = valid_acceptance()
    gate = document["local_runtime_gate"]  # type: ignore[assignment]
    gate["status"] = "not_applicable"  # type: ignore[index]
    gate["rationale"] = (  # type: ignore[index]
        "WP-01 claims no runnable behavior even though it owns the web shell dependency."
    )
    subgates = gate["subgates"]  # type: ignore[index]
    subgates["frozen_lock_start_health_shutdown"] = {  # type: ignore[index]
        "status": "not_applicable",
        "rationale": "WP-01 incorrectly claims its owned runnable web shell is documentation only.",
    }
    errors = list(
        Draft202012Validator(schema("integration-acceptance-v1.schema.json")).iter_errors(document)
    )
    assert errors
    with pytest.raises(validate_evidence.EvidenceError, match="runnable web shell"):
        validate_evidence.validate_local_runtime_acceptance(document)


def test_accepted_wp_01_rejects_empty_components() -> None:
    document = valid_acceptance()
    document["local_runtime_gate"]["components"] = []  # type: ignore[index]
    errors = list(
        Draft202012Validator(schema("integration-acceptance-v1.schema.json")).iter_errors(document)
    )
    assert errors
    with pytest.raises(validate_evidence.EvidenceError, match="owned components"):
        validate_evidence.validate_local_runtime_acceptance(document)


def test_accepted_wp_01_requires_passing_runtime_validation_row() -> None:
    document = valid_acceptance()
    document["validation"] = [{"id": "UNIT", "result": "passed", "exit_code": 0}]
    errors = list(
        Draft202012Validator(schema("integration-acceptance-v1.schema.json")).iter_errors(document)
    )
    assert errors
    with pytest.raises(validate_evidence.EvidenceError, match="passing LOCAL-RUNTIME validation"):
        validate_evidence.validate_local_runtime_acceptance(document)


def test_accepted_wp_01_rejects_nonexistent_runtime_evidence() -> None:
    document = valid_acceptance()
    document["local_runtime_gate"]["evidence"] = [  # type: ignore[index]
        f"docs/evidence/wp-01/runtime/does-not-exist#sha256:{'0' * 64}"
    ]
    with pytest.raises(validate_evidence.EvidenceError, match="does not exist"):
        validate_evidence.validate_local_runtime_acceptance(document)


def test_wp_02_allows_exact_ownership_not_applicable_runtime() -> None:
    document = valid_acceptance()
    document["work_package"] = "WP-02"
    gate = document["local_runtime_gate"]  # type: ignore[assignment]
    gate["status"] = "not_applicable"  # type: ignore[index]
    gate["rationale"] = (  # type: ignore[index]
        "WP-02 owns documentation-only contracts and depends on WP-03 for the first runtime."
    )
    subgates = gate["subgates"]  # type: ignore[index]
    subgates["frozen_lock_start_health_shutdown"] = {  # type: ignore[index]
        "status": "not_applicable",
        "rationale": "WP-02 owns no runnable component and depends on WP-03 for runtime startup.",
    }
    Draft202012Validator(schema("integration-acceptance-v1.schema.json")).validate(document)
    validate_evidence.validate_local_runtime_acceptance(document)


def test_committed_runtime_evidence_is_complete_and_checksummed() -> None:
    trace = verify_runtime_evidence.verify(ROOT / "docs/evidence/wp-01/runtime")
    assert trace["result"] == "passed"


def test_runtime_evidence_rejects_tampered_response(tmp_path: Path) -> None:
    runtime_copy = tmp_path / "runtime"
    shutil.copytree(ROOT / "docs/evidence/wp-01/runtime", runtime_copy)
    (runtime_copy / "page-body.html").write_text("tampered", encoding="utf-8")
    with pytest.raises(verify_runtime_evidence.RuntimeEvidenceError, match="checksum mismatch"):
        verify_runtime_evidence.verify(runtime_copy)


def test_generic_not_applicable_local_runtime_rationale_fails_semantics() -> None:
    document = valid_acceptance()
    subgates = document["local_runtime_gate"]["subgates"]  # type: ignore[index]
    subgates["offline_agent_api_and_stream"]["rationale"] = (  # type: ignore[index]
        "This particular gate does not apply at the present time."
    )
    with pytest.raises(validate_evidence.EvidenceError, match="ownership or dependency"):
        validate_evidence.validate_local_runtime_acceptance(document)


def build_record(
    workspace: str,
    *,
    commands: tuple[str, ...] | None = None,
    generated_sha256: str = "e" * 64,
) -> rebuild_foundation.BuildRecord:
    expected = tuple(" ".join(command) for command in rebuild_foundation.BUILD_COMMANDS)
    return rebuild_foundation.BuildRecord(
        label=Path(workspace).name,
        workspace_root=workspace,
        clean_start=True,
        commands=commands or expected,
        build_id="wp01-input-identity",
        preview_seed_sha256="b" * 64,
        workspace_path_canonicalization="/workspace",
        generated_file_count=5,
        generated_sha256=generated_sha256,
        archive_sha256="f" * 64,
        log_sha256="a" * 64,
    )


def test_reproducibility_rejects_archive_twice_from_one_workspace() -> None:
    records = (build_record("/tmp/same"), build_record("/tmp/same"))
    with pytest.raises(rebuild_foundation.ReproducibilityError, match="archive-twice"):
        rebuild_foundation.verify_independent_builds(records)


def test_reproducibility_requires_build_commands_in_both_workspaces() -> None:
    records = (
        build_record("/tmp/build-a"),
        build_record("/tmp/build-b", commands=("build_foundation_artifact.py",)),
    )
    with pytest.raises(rebuild_foundation.ReproducibilityError, match="frozen build command"):
        rebuild_foundation.verify_independent_builds(records)


def test_reproducibility_rejects_different_generated_outputs() -> None:
    records = (
        build_record("/tmp/build-a"),
        build_record("/tmp/build-b", generated_sha256="0" * 64),
    )
    with pytest.raises(rebuild_foundation.ReproducibilityError, match="generated artifact"):
        rebuild_foundation.verify_independent_builds(records)


def test_artifact_allows_internal_pnpm_parent_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "315532800")
    root = tmp_path / "root"
    target = root / "apps/web/.next/standalone/node_modules/.pnpm/pkg/index.js"
    target.parent.mkdir(parents=True)
    target.write_text("module.exports = {}\n", encoding="utf-8")
    link = root / "apps/web/.next/standalone/apps/web/node_modules/pkg"
    link.parent.mkdir(parents=True)
    link.symlink_to("../../../node_modules/.pnpm/pkg")
    entries = build_foundation_artifact.build(root, tmp_path / "artifact.tar.gz")
    assert any(entry["type"] == "symlink" for entry in entries)


def test_artifact_rejects_symlink_that_escapes_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "315532800")
    root = tmp_path / "root"
    link = root / "apps/web/escape"
    link.parent.mkdir(parents=True)
    link.symlink_to("../../../outside")
    with pytest.raises(ValueError, match="unsafe symlink"):
        build_foundation_artifact.build(root, tmp_path / "artifact.tar.gz")


def test_isolated_workspace_prefixes_are_canonicalized(tmp_path: Path) -> None:
    root_a = tmp_path / "build-a"
    root_b = tmp_path / "build-b"
    file_a = root_a / "apps/web/generated.json"
    file_b = root_b / "apps/web/generated.json"
    file_a.parent.mkdir(parents=True)
    file_b.parent.mkdir(parents=True)
    file_a.write_text(f'{{"root":"{root_a.resolve()}"}}', encoding="utf-8")
    file_b.write_text(f'{{"root":"{root_b.resolve()}"}}', encoding="utf-8")
    assert build_foundation_artifact.canonical_payload(
        root_a, file_a
    ) == build_foundation_artifact.canonical_payload(root_b, file_b)


def test_next_build_entropy_is_derived_only_from_input_identity(tmp_path: Path) -> None:
    first = rebuild_foundation.seed_deterministic_next_inputs(tmp_path / "a", "f" * 64)
    second = rebuild_foundation.seed_deterministic_next_inputs(tmp_path / "b", "f" * 64)
    assert first == second


def test_sbom_normalization_removes_raw_and_file_uri_checkout_paths(tmp_path: Path) -> None:
    workspace = tmp_path / "checkout with spaces"
    workspace.mkdir()
    sbom = tmp_path / "sbom.json"
    sbom.write_text(
        json.dumps(
            {
                "components": [
                    {
                        "name": "workspace",
                        "version": "0.0.0",
                        "properties": [{"name": "path", "value": str(workspace / "apps")}],
                        "externalReferences": [
                            {"type": "distribution", "url": (workspace / "packages").as_uri()}
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    normalize_sbom.normalize(sbom, workspace)
    rendered = sbom.read_text(encoding="utf-8")
    assert str(workspace) not in rendered
    assert workspace.as_uri() not in rendered
    assert "/workspace/apps" in rendered
    assert "file:///workspace/packages" in rendered


def test_secret_finding_never_echoes_value() -> None:
    secret = "AKIA" + "ABCDEFGHIJKLMNOP"
    findings = scan_secrets.scan_text("fixture", f"key={secret}")
    assert findings
    assert all(secret not in finding for finding in findings)


def test_placeholder_generic_secret_is_allowed() -> None:
    assert scan_secrets.scan_text("fixture", 'api_key="placeholder"') == []


def test_extra_handoff_field_is_rejected() -> None:
    document = copy.deepcopy(valid_handoff())
    document["surprise"] = True
    errors = list(Draft202012Validator(schema("handoff-v1.schema.json")).iter_errors(document))
    assert errors


def valid_trivy_license_report() -> dict[str, object]:
    def row(package: str, file_path: str, license_name: str = "MIT") -> dict[str, object]:
        return {
            "Severity": "LOW",
            "Category": "notice",
            "PkgName": package,
            "FilePath": file_path,
            "Name": license_name,
            "Text": "",
            "Confidence": 1,
            "Link": "",
        }

    return {
        "SchemaVersion": 2,
        "ArtifactName": ".",
        "ArtifactType": "filesystem",
        "Results": [
            {
                "Target": "Node.js",
                "Class": "license",
                "Licenses": [
                    row(
                        "@cyclonedx/cdxgen",
                        "node_modules/.pnpm/cdxgen/node_modules/@cyclonedx/cdxgen/package.json",
                        "Apache-2.0",
                    ),
                    row("next", "node_modules/.pnpm/next/node_modules/next/package.json"),
                    row("react", "node_modules/.pnpm/react/node_modules/react/package.json"),
                ],
            },
            {
                "Target": "Python",
                "Class": "license",
                "Licenses": [
                    row(
                        "cyclonedx-bom",
                        ".venv/lib/python3.12/site-packages/cyclonedx_bom.dist-info/METADATA",
                        "Apache-2.0",
                    ),
                    row(
                        "fastapi",
                        ".venv/lib/python3.12/site-packages/fastapi.dist-info/METADATA",
                    ),
                    row(
                        "pydantic-ai-slim",
                        ".venv/lib/python3.12/site-packages/pydantic_ai_slim.dist-info/METADATA",
                    ),
                ],
            },
        ],
    }


def test_trivy_license_evidence_requires_both_installed_ecosystems() -> None:
    assert validate_trivy.validate(valid_trivy_license_report()) == (6, 3, 3)


def test_trivy_license_evidence_rejects_zero_rows() -> None:
    report = valid_trivy_license_report()
    for result in report["Results"]:  # type: ignore[union-attr]
        result["Licenses"] = []
    with pytest.raises(validate_trivy.TrivyValidationError, match="zero license"):
        validate_trivy.validate(report)


def test_trivy_license_evidence_rejects_missing_python_coverage() -> None:
    report = valid_trivy_license_report()
    report["Results"] = report["Results"][:1]  # type: ignore[index]
    with pytest.raises(validate_trivy.TrivyValidationError, match=r"Python.*partial"):
        validate_trivy.validate(report)


def test_trivy_license_evidence_rejects_missing_node_coverage() -> None:
    report = valid_trivy_license_report()
    report["Results"] = report["Results"][1:]  # type: ignore[index]
    with pytest.raises(validate_trivy.TrivyValidationError, match=r"Node.*partial"):
        validate_trivy.validate(report)


def test_trivy_license_evidence_rejects_malformed_row() -> None:
    report = valid_trivy_license_report()
    report["Results"][0]["Licenses"][0]["FilePath"] = ""  # type: ignore[index]
    with pytest.raises(validate_trivy.TrivyValidationError, match="non-empty FilePath"):
        validate_trivy.validate(report)


def test_trivy_license_evidence_rejects_denied_license() -> None:
    report = valid_trivy_license_report()
    report["Results"][0]["Licenses"][0]["Name"] = "GPL-3.0-only"  # type: ignore[index]
    with pytest.raises(validate_trivy.TrivyValidationError, match="denied licenses"):
        validate_trivy.validate(report)


def test_trivy_license_evidence_retains_reviewable_lgpl_without_suppressing_it() -> None:
    report = valid_trivy_license_report()
    report["Results"][0]["Licenses"][0].update(  # type: ignore[index,union-attr]
        {"Name": "LGPL-3.0-or-later", "Severity": "HIGH"}
    )
    assert validate_trivy.validate(report) == (6, 3, 3)


def test_undici_lock_policy_accepts_only_patched_resolutions() -> None:
    manifest = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    lock = yaml.safe_load((ROOT / "pnpm-lock.yaml").read_text(encoding="utf-8"))
    assert verify_lockfiles.validate_undici_security(manifest, lock) == ("7.29.0", "8.10.0")


def test_undici_lock_policy_rejects_vulnerable_resolution() -> None:
    manifest = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    lock = yaml.safe_load((ROOT / "pnpm-lock.yaml").read_text(encoding="utf-8"))
    lock["packages"]["undici@7.28.0"] = {}
    with pytest.raises(ValueError, match=r"advisory-vulnerable undici@7[.]28[.]0"):
        verify_lockfiles.validate_undici_security(manifest, lock)


def test_undici_lock_policy_rejects_override_drift() -> None:
    manifest = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    lock = yaml.safe_load((ROOT / "pnpm-lock.yaml").read_text(encoding="utf-8"))
    del manifest["pnpm"]["overrides"]["cheerio@1.2.0>undici"]
    with pytest.raises(ValueError, match="exactly the reviewed undici overrides"):
        verify_lockfiles.validate_undici_security(manifest, lock)


def test_trivy_workflow_install_scan_validate_upload_order_is_static_policy() -> None:
    assert validate_workflows.main() == 0
