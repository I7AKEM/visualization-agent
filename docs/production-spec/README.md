# Production Visualization Agent — implementation specification index

Status: normative round-three specification; WP-00 governance baseline recorded; runtime implementation has not started
Baseline date: 2026-08-29
Repository runtime baseline: `pydantic-ai-slim[anthropic,openai,mcp]==2.35.3`
Lifecycle research baseline: Pydantic AI 2.36.0; version-sensitive behavior must be verified against 2.35.3 or upgraded through ADR-001.

## 1. Purpose and truth hierarchy

This directory converts `PRODUCTION_PLAN.md` from an architecture plan into an implementation contract. Engineers implement these decisions; they do not silently choose alternate frameworks, states, retry rules, storage meanings, model authority, or failure behavior.

When two sources conflict, use this order:

1. security, privacy, legal, and tenant-isolation requirements;
2. typed contracts and invariants in `02_CONTRACTS_AND_STATE_MACHINES.md`;
3. test and release gates in `03_TEST_AND_FAILURE_MATRIX.md` and `04_AGENT_EVAL_SPEC.md`;
4. operational, delivery, ownership, and integration requirements in `05_SECURITY_OPERATIONS_AND_DELIVERY.md` and `06_TASK_DISPATCH_BRIEFS.md`;
5. this index and `PRODUCTION_PLAN.md`;
6. dependency documentation and examples;
7. prompts, retrieved skills, model output, and informal comments.

No model, skill, MCP server, UI client, or cached artifact can override levels 1–5.

## 2. Honest quality claim

“No bugs” cannot be guaranteed for an evolving distributed system or every possible future input. The enforceable production claim is:

- no known severity-0 or severity-1 defects;
- no open correctness, tenant-isolation, unauthorized-disclosure, arbitrary-code-execution, or silent-data-change defect;
- 100% pass on critical deterministic cases and invariants;
- all supported input equivalence classes covered by examples plus boundary cases;
- unknown combinations exercised using property, fuzz, metamorphic, model-based, chaos, and differential tests;
- unsupported behavior rejects safely with a typed error and user action—never an invented result;
- every production failure is classified, contained, converted into a regression case, and tracked to closure.

A release that does not have evidence for these statements is not production-grade even if the demo works.

## 3. Normative documents

| Document | Owns |
|---|---|
| [`PRODUCTION_PLAN.md`](../../PRODUCTION_PLAN.md) | product direction, researched ecosystem, renderer choices, roadmap |
| [`01_DECISIONS_AND_ARCHITECTURE.md`](01_DECISIONS_AND_ARCHITECTURE.md) | frozen decisions, responsibilities, trust boundaries, modes, topology |
| [`02_CONTRACTS_AND_STATE_MACHINES.md`](02_CONTRACTS_AND_STATE_MACHINES.md) | exact domain objects, API/stream contracts, state transitions, clarification, idempotency, revisions |
| [`03_TEST_AND_FAILURE_MATRIX.md`](03_TEST_AND_FAILURE_MATRIX.md) | code-level test strategy, equivalence classes, failure injection, CI gates |
| [`04_AGENT_EVAL_SPEC.md`](04_AGENT_EVAL_SPEC.md) | agent datasets, case schema, evaluators, thresholds, model/prompt comparison |
| [`05_SECURITY_OPERATIONS_AND_DELIVERY.md`](05_SECURITY_OPERATIONS_AND_DELIVERY.md) | threat controls, telemetry, SLOs, alerts, incidents, deployment, rollback, work packages |
| [`06_TASK_DISPATCH_BRIEFS.md`](06_TASK_DISPATCH_BRIEFS.md) | fresh-context task prompts, path ownership, dependency waves, integration handoff |

## 4. Fixed product identity

Name/category: **Visualization Agent / Visual Analytics Workspace**.

It is not:

- an autonomous general-purpose data agent;
- a code-generation environment;
- a replacement for governed metrics or source systems;
- an MCP wrapper around AntV's public chart service;
- a system that sends every request through an LLM;
- a place where a plausible narrative can substitute for computed evidence.

It provides five explicit modes:

1. `render_only`: exact source rows/values, no computation or value-changing operation;
2. `visual_transform`: approved deterministic preparation for visualization;
3. `analyze`: verified metrics, comparisons, statistics, and insights;
4. `compose`: dashboards, reports, and infographics from existing artifacts;
5. `revise`: presentation, binding, composition, transformation, or analytical revision.

## 5. Fixed stack

The first production implementation uses:

- Python 3.12;
- Pydantic Validation and Pydantic Settings;
- Pydantic AI with a version freeze/compatibility gate;
- FastAPI asynchronous API;
- Vercel AI Data Stream-compatible SSE for the browser;
- Next.js 16.3.3 target, React 19.2 target, and TypeScript strict mode;
- AI SDK 7 target for UI state/transport and Ant Design X 2.8/Ant Design 6.4 target for the product shell;
- GPT-Vis/G2 for common charts, S2 for pivots, Mapbox GL JS through `react-map-gl`, optional lazy deck.gl, G6/Graphin, AntV Infographic, and allowlisted React widgets;
- Arrow/Parquet and isolated DuckDB workers for uploads;
- Ibis typed expression compilation where the coverage spike passes;
- Postgres for authoritative metadata, artifact state, audit, and outbox;
- Redis for ephemeral rate limits, leases, and cache—not authoritative state;
- S3-compatible object storage for immutable source/canonical/result/export blobs;
- Logfire/OpenTelemetry for application, agent, model, tool, worker, and infrastructure traces;
- Pydantic Evals for offline and sampled online evaluation;
- containerized services with Postgres-authoritative interactive state and DBOS background durability/queues.

For every target expressed as a major/minor above, WP-01 installs the latest non-prerelease patched release available on the dependency-lock pull request date, commits that exact lock, records it in the version manifest, and uses that immutable artifact through staging and production. If Pydantic AI 2.36.0's Vercel stream adapter fails the golden AI SDK 7 protocol suite, WP-01 pins the latest non-prerelease AI SDK major that the Pydantic integration supports and records the compatibility exception; engineers must not write an ad hoc stream adapter. No dependency is considered adopted until its exact version, license, SBOM entry, compatibility tests, and fallback behavior are recorded.

## 6. Frozen ADR outcomes and required owner inputs

| ADR | Frozen engineering decision | Blocking owner input/evidence |
|---|---|---|
| ADR-001 | upgrade once to exactly Pydantic AI 2.36.0 before feature work; stop if the compatibility suite fails | approval of the dependency PR and preserved compatibility report |
| ADR-002 | Postgres owns interactive state/outbox; DBOS owns background profile/analysis/export/cleanup durability | production Postgres sizing/backup and DBOS recovery/load evidence |
| ADR-003 | release 1 uses GPT-Vis + G2; Flint is a post-release evaluation and cannot block implementation | none for release 1 |
| ADR-004 | deploy OCI containers on managed Kubernetes with managed Postgres/Redis/object storage and OTel Collector | organization selects cloud account, data region, domains, network/identity ownership |
| ADR-005 | map joins require a versioned authoritative/licensed boundary source; feature remains disabled until supplied | data owner supplies Saudi boundary dataset, license, bilingual stable IDs, update owner |
| ADR-006 | first governed integration uses the customer's existing approved semantic layer; if none exists, governed connectors are deferred rather than inventing metrics | data owner selects source, metrics, access policy, and steward |
| ADR-007 | implementation work is split into one isolated Codex task/worktree per work package, dispatched in dependency waves, with one integration owner | access to create worktrees/tasks and an integration reviewer |
| ADR-008 | production identity uses OIDC Authorization Code + PKCE with server-derived authority; provider and claim/policy ownership are not guessed | identity owner selects the IdP, claim/role contract, session/revocation rules, and support ownership; production auth remains disabled until accepted |

These owner inputs are governance facts, not implementation choices. Missing input disables the dependent feature; engineers do not guess. An ADR amendment cannot weaken a security or quality invariant.

## 7. Required repository structure

Implementation creates this structure exactly; renaming requires an ADR because paths are used by CI and evidence tooling.

```text
apps/
  web/                         # Next.js UI
services/
  api/                         # FastAPI/Pydantic AI/streaming
  worker_analysis/             # isolated profile/query/spatial work
  worker_export/               # private image/PDF export
packages/
  contracts_py/                # Pydantic domain/API/event models
  contracts_ts/                # generated TypeScript/JSON Schema bindings
  renderer_registry/           # React renderer adapters and validators
  evals/                       # Pydantic Evals tasks/evaluators
datasets/
  eval/                        # versioned synthetic/de-identified eval cases
  fixtures/                    # deterministic file/map/calendar fixtures
infra/
  containers/
  migrations/
  otel/
  dashboards/
  alerts/
docs/
  adr/
  runbooks/
  production-spec/
tests/
  contract/
  integration/
  e2e/
  security/
  performance/
  chaos/
```

Generated TypeScript contracts must come from versioned JSON Schema emitted by `contracts_py`; hand-written duplicates are forbidden.

## 8. Definition of “implementation-ready”

A work package may enter coding only when it has:

- a named owner and reviewer;
- linked normative contract/state transition;
- explicit inputs, outputs, dependencies, permissions, timeouts, budgets, and errors;
- deterministic acceptance tests and relevant eval cases identified before implementation;
- telemetry spans/metrics and redaction classification;
- migration and rollback behavior;
- no unresolved ADR that changes its behavior.

If an implementation question is not answered by these documents, the engineer must open an ADR/spec amendment. They must not decide silently in code.

## 9. Evidence packet required for every release

- immutable release ID linking code commit, container digests, schema version, migrations, dependency locks, model catalog, prompt/skill versions, eval dataset/evaluator versions, and configuration hash;
- unit/property/fuzz/contract/integration/E2E/security/accessibility/visual/load/chaos reports;
- offline Pydantic Evals report with per-slice and critical-case results;
- SBOM, dependency/image/license/secret scan results;
- telemetry/redaction verification with correlated example traces;
- migration, backup/restore, restart/resume, reconnect/replay, and rollback evidence;
- staging smoke and canary comparison report;
- approved residual-risk register and on-call/runbook links.

## 10. First-party implementation references

- [Pydantic AI testing](https://pydantic.dev/docs/ai/guides/testing/)
- [Pydantic AI deferred tools and approval](https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/)
- [Pydantic AI durable execution](https://pydantic.dev/docs/ai/capabilities/durable_execution/overview/)
- [Pydantic AI Vercel data stream](https://pydantic.dev/docs/ai/integrations/ui/vercel-ai/)
- [Pydantic Evals](https://pydantic.dev/docs/ai/evals/evals/)
- [Span-based evaluation](https://pydantic.dev/docs/ai/evals/evaluators/span-based/)
- [Agentic evaluators](https://pydantic.dev/docs/ai/evals/evaluators/agentic/)
- [Online evaluation](https://pydantic.dev/docs/ai/evals/online-evaluation/)
- [Logfire AI observability](https://logfire.pydantic.dev/docs/ai-observability/)
