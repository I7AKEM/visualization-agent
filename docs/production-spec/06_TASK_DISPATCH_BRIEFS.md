# Production Visualization Agent — isolated task dispatch briefs

Status: normative implementation coordination contract
Applies to: `WP-00` through `WP-14`

## 1. Dispatch rule

Create one Codex task and one Git worktree per work package. Use a fresh context. Start the worktree from the integration branch containing the latest accepted dependency artifacts. Never start a dependent task from an older work-package branch and never make two tasks responsible for the same generated artifact.

Only the integration task merges branches. Work-package tasks implement, test, commit, and return evidence; they do not merge, deploy, or silently revise another package's contract.

## 2. Canonical fresh-context prompt

Use this prompt, replacing every angle-bracket field. Do not copy chat history into the task.

```text
Implement <WP-ID — exact title> for the Production Visualization Agent in this isolated worktree.

Before editing, read these repository documents completely in this order:
1. docs/production-spec/README.md
2. docs/production-spec/01_DECISIONS_AND_ARCHITECTURE.md
3. docs/production-spec/02_CONTRACTS_AND_STATE_MACHINES.md
4. docs/production-spec/03_TEST_AND_FAILURE_MATRIX.md
5. docs/production-spec/04_AGENT_EVAL_SPEC.md
6. docs/production-spec/05_SECURITY_OPERATIONS_AND_DELIVERY.md
7. docs/production-spec/06_TASK_DISPATCH_BRIEFS.md
8. PRODUCTION_PLAN.md for lower-precedence normative product direction and supporting research context.

Treat documents 1–7 as normative in the precedence order declared by README.md. Implement only <WP-ID> and its owned paths. Its dependency evidence is available at <dependency-evidence paths/commit>. Do not guess organization facts or weaken a gate. If a required owner input is absent, keep the feature disabled with the specified typed behavior and report the missing input.

Preserve unrelated user changes. Do not use agent/model output as executable code, SQL, renderer code, authorization, or approval. Add deterministic code tests and the required eval cases for every affected model behavior. Run every applicable gate locally; distinguish tests actually run from tests requiring CI or external infrastructure.

Commit the substantive delivery first, then commit one handoff-only packet using the two-commit protocol in section 5. The packet contains: the substantive delivery commit, changed paths, requirement IDs, exact commands/results, eval dataset changes/results, migration and compatibility notes, configuration/secret names without values, observability changes, known risks/disabled features, and rollback steps. A submitted packet uses `handoff_commit: null`; only the integration owner records the now-known handoff commit during acceptance. Do not claim zero bugs; fail the task if a critical gate is not proven.
```

## 3. Ownership and task-specific briefs

The listed paths are primary ownership, not permission to change frozen contracts. A task may add tests beside owned code. Changes outside primary ownership require the integration owner to update this matrix before dispatch.

| Task | Primary owned paths | Required output beyond code | Must not do |
|---|---|---|---|
| `WP-00` governance and baselines | `docs/governance/**`, `docs/adr/**`, `docs/evidence/wp-00/**` | POC inventory; owner-input checklist; classifications, retention, SLO/limit acceptance; disabled-feature register; traceability skeleton | invent IdP/cloud/region/boundary/semantic-layer decisions; modify POC runtime |
| `WP-01` monorepo, dependency, CI | root manifests/locks; `.github/**`; `apps/**`/`services/**`/`packages/**` scaffolds; `infra/dev/**`; `docs/evidence/wp-01/**` | exact version/license/SBOM manifest; adapter compatibility report; reproducible empty builds | implement product behavior; write an ad hoc stream adapter; delete POC files |
| `WP-02` contracts/generated clients | `packages/contracts_py/**`, `packages/contracts_ts/**`, `schemas/**`, contract tests, `docs/evidence/wp-02/**` | generated-client checksum; compatibility diff; requirement-to-schema map | add business execution, UI, or storage behavior; hand-edit generated outputs |
| `WP-03` identity/policy/audit/state | `services/api/src/{identity,policy,state,audit,outbox}/**`, migrations for owned tables, integration tests, `docs/evidence/wp-03/**` | authorization matrix; migration/replay/idempotency evidence | store source/result blobs in Postgres; use client approval as authorization |
| `WP-04` ingestion/profile | `services/api/src/ingestion/**`, `services/worker_analysis/src/profile/**`, upload/profile fixtures, `docs/evidence/wp-04/**` | format/encoding/limit matrix; canonicalization and cleanup evidence | expose unscanned files; infer ambiguous calendar/geography as fact |
| `WP-05` exact-render slice | `apps/web/**` shell/stream/exact flow, `services/api/src/commands/exact/**`, initial adapters in `packages/renderer_registry/**`, exact fixtures, `docs/evidence/wp-05/**` | source-view/exact-proof evidence; reconnect/RTL/a11y/visual artifacts | add transforms/aggregation/sort/sampling; execute model output |
| `WP-06` model catalog/logical agents/eval corpus | `services/api/src/agents/**`, `packages/evals/**`, `datasets/eval/**`, prompt/skill registries, `docs/evidence/wp-06/**` | frozen 2,400-case manifest and split hashes; model/prompt/provider comparison | implement numeric truth or renderer execution inside an agent; call live models in ordinary tests |
| `WP-07` transform/analysis engine | `services/worker_analysis/src/{transform,analysis}/**`, compiler/adapters, evidence/reconciliation code, numeric fixtures, `docs/evidence/wp-07/**` | differential/metamorphic/numeric/load/chaos evidence | execute arbitrary code/SQL; publish unreconciled results |
| `WP-08` renderer registry | `packages/renderer_registry/**` beyond WP-05 adapters, dashboard/S2/G2/KPI components, renderer fixtures, `docs/evidence/wp-08/**` | capability/fallback matrix; skill-version trace; visual/a11y/performance artifacts | create a universal lowest-common-denominator spec; allow arbitrary callbacks/HTML |
| `WP-09` map/temporal/calendar | `packages/renderer_registry/src/{map,temporal}/**`, matching `apps/web/**` map/time controls, spatial worker modules, geo/time fixtures, `docs/evidence/wp-09/**` | boundary/calendar version manifests; privacy and temporal-join evidence | edit WP-08-owned generated registry/catalog files; enable authoritative choropleths without approved boundaries; silently convert ambiguous dates |
| `WP-10` clarification/approval/revision | `services/api/src/{clarification,approval,revision}/**`, matching UI flows, trajectory fixtures, `docs/evidence/wp-10/**` | resume/restart/rebase/branch/undo evidence; external-agent relay tests | treat approval as auth; overwrite stale revisions; keep an indefinite waiting run |
| `WP-11` governed data/MCP | `services/api/src/{semantic,mcp}/**`, connector policies/adapters, `services/mcp/**`, `docs/evidence/wp-11/**` | read-only/dry-run/lineage/SSRF/access evidence; tool capability manifest | invent business metrics; expose generic SQL/filesystem/shell tools; send data to public chart services |
| `WP-12` export/infographic | `services/worker_export/**`, export/infographic adapters/templates/fixtures, `docs/evidence/wp-12/**` | fidelity/security/font/RTL/load evidence; provenance manifest | load public assets at render time; export unapproved draft without watermark |
| `WP-13` observability/online eval/runbooks | telemetry libraries/config, `infra/observability/**`, `docs/runbooks/**`, online-eval jobs, `docs/evidence/wp-13/**` | redaction review; dashboard/alert/canary/drill artifacts; evaluator health | log source rows/prompts/secrets by default; make optional provider health a fatal readiness dependency |
| `WP-14` hardening/release | release workflows/manifests, `infra/environments/**`, `docs/evidence/release/**` | signed consolidated release packet; canary/rollback/backup/restore results | waive a critical gate; deploy a different artifact than the tested digest |

## 4. Dependency evidence contract

A dependency is usable only when its integration commit has:

- `docs/evidence/<wp-id>/handoff.yaml` validated against the handoff schema and its delivery/handoff Git relationships;
- a green CI run for that exact commit/digest;
- contract/schema/version manifests with checksums;
- no unresolved severity-0/1 or critical-gate failure;
- an integration-owner acceptance record at `docs/evidence/integration/<wp-id>-acceptance.yaml`.

The dependent task prompt names the substantive delivery commit, handoff commit, integration acceptance commit, and evidence paths. “Another task said it was done” is not dependency evidence.

`WP-00` is the only bootstrap exception to the green-CI rule because `WP-01` creates the CI foundation. The integration owner MAY conditionally accept `WP-00` for owner-independent `WP-01` scaffolding after documentation, YAML, ownership, ancestry, and POC-preservation checks pass. That acceptance MUST keep production and every owner-dependent capability disabled, MUST list every unresolved owner input, and MUST NOT be reused as production approval or release evidence.

## 5. Handoff schema

Every task writes `docs/evidence/<wp-id>/handoff.yaml` with these required keys:

```yaml
schema_version: 1
work_package: WP-00
base_integration_commit: "<40-hex>"
delivery_commit: "<40-hex>"
handoff_commit: null
handoff_state: submitted
changed_paths: []
requirements: []
dependency_commits: {}
commands_run:
  - command: "<literal command>"
    exit_code: 0
    result: "<short factual result>"
tests_not_run: []
eval_manifest_versions: []
migrations: []
configuration_keys: []
secret_names: []
telemetry_changes: []
disabled_features: []
known_risks: []
rollback_steps: []
critical_gates_passed: []
reviewers_required: []
```

### 5.1 Non-self-referential commit semantics

The Git anchors have separate meanings and MUST NOT be collapsed:

1. `base_integration_commit` is the accepted integration commit from which the isolated task started.
2. `delivery_commit` is the substantive work-package commit. `git diff --name-only <base_integration_commit> <delivery_commit>` MUST equal `changed_paths`; the handoff file is excluded unless it was already substantive input owned by that package.
3. The work-package task then creates one direct child commit that changes only `docs/evidence/<wp-id>/handoff.yaml`. This is the submitted handoff commit. Because a commit cannot contain its own hash, the submitted file MUST use `handoff_commit: null` and `handoff_state: submitted`.
4. The integration owner resolves the submitted handoff commit from Git, verifies that its parent is `delivery_commit` and that its diff is handoff-only, then records the 40-hex hash in the handoff file as part of a later integration acceptance commit. The accepted file uses `handoff_state: accepted` or `conditionally_accepted`; a rejected packet uses `rejected`.
5. The integration acceptance commit is the commit that first adds `docs/evidence/integration/<wp-id>-acceptance.yaml`. It is deliberately not embedded in that same file. Resolve it with `git log --diff-filter=A --format=%H -- docs/evidence/integration/<wp-id>-acceptance.yaml`, and use that commit—or a later accepted integration descendant—as the dependent task base.

This sequence is deterministic: no file is required to contain the hash of the commit that creates that file. An integration annotation does not rewrite the historical meaning of `delivery_commit` or `handoff_commit`.

### 5.2 Integration acceptance record

Every accepted or conditionally accepted package has an integration-owned record with at least:

```yaml
schema_version: 1
record_type: integration_acceptance
work_package: WP-00
status: accepted # accepted | conditionally_accepted | rejected
acceptance_base_commit: "<40-hex>"
delivery_commit: "<40-hex>"
handoff_commit: "<40-hex>"
specification_commit: "<40-hex>"
acceptance_scope: {}
validation: []
unresolved_owner_inputs: []
disabled_features: []
conditions: []
rollback_steps: []
dependent_task_base_rule: acceptance_record_introduction_commit
```

`acceptance_base_commit` is the integration head immediately before the acceptance commit, so it is knowable without self-reference. `specification_commit` is the exact normative specification revision used for review. Conditional acceptance MUST narrow `acceptance_scope` and preserve every affected disable rule. CI rejects placeholders, missing arrays, dirty generated artifacts, an invalid base/delivery/handoff ancestry or path relationship, an accepted handoff without an acceptance record, or a claimed gate without its machine-readable result.

WP-01 owns `schemas/handoff-v1.schema.json` and `schemas/integration-acceptance-v1.schema.json`, generated from this section and validated in CI. WP-00 requirement IDs come from `docs/governance/requirements-traceability.yaml`; WP-02 expands the repository-wide stable requirement registry at `tests/requirements.yaml`. A handoff may cite only IDs present in the applicable committed registry.

## 6. Integration task brief

The integration task is a separate fresh-context task, but it is not a work-package implementation task. Its prompt is:

```text
Act as integration owner for the Production Visualization Agent. Read the seven normative documents completely. Inspect a submitted work-package delivery commit and handoff-only commit. Verify ownership, dependencies, schemas, migrations, tests/evals, security, observability, rollback, and the Git relationships in section 5. Merge only in the documented wave/dependency order. After merge, run the receiving branch's applicable full gates, annotate the resolved handoff commit, and write an integration acceptance record. Reject or return the branch for correction if any critical evidence is absent. Never repair a work package by silently changing its contract; send the correction to that isolated task.
```

The integration task never combines user feedback threads: it records only accepted evidence and sends defects back to the originating work-package task.
