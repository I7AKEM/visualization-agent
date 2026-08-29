# Contracts and state machines

All persisted/API/event types use strict Pydantic models (`extra='forbid'`, strict scalar validation where coercion can change meaning) and versioned JSON Schema. TypeScript types and validators are generated from those schemas. Examples below are normative field definitions even where compact notation is used.

## 1. Universal conventions

- IDs: UUIDv7 lowercase strings. Resource IDs are server generated; `command_id`, `answer_id`, and other fields explicitly designated for retry identity are client generated and validated.
- Timestamps: RFC 3339 UTC with microseconds and `Z`.
- Dates: ISO `YYYY-MM-DD`, never implicit UTC midnight.
- Durations: integer milliseconds with `_ms` suffix.
- Sizes: integer bytes with `_bytes` suffix.
- Hashes: `sha256:<lowercase hex>` over canonical bytes; hash algorithm is never implicit.
- Money: decimal string plus ISO 4217 currency; never binary float.
- Ratios: decimal string plus explicit scale (`fraction`, `percent`, `basis_point`).
- Coordinates: `[longitude, latitude]` decimal numbers in WGS84 unless a declared source CRS is being ingested.
- Pagination: opaque cursor; never an unbounded array endpoint.
- Schemas/events: positive integer `schema_version`; incompatible changes create a new version and adapter.
- Optional means semantically absent; `null` is not interchangeable with missing unless documented.
- Enums reject unknown values. Clients receiving a future event type preserve cursor/state and show an upgrade-required error.

## 2. Common enums

```text
DataMode = exact | transformed | aggregated | sampled
RequestKind = render | transform | analyze | compose | revise | unlock_exact | clarify_answer | approve | cancel
ArtifactKind = chart | kpi | table | pivot | map | graph | infographic | dashboard | report | narrative
ArtifactStatus = draft | preview | provisional | final | superseded | failed | cancelled
RevisionKind = presentation | binding | composition | transform | analytical
RunStatus = accepted | validating | input_required | approval_required | queued | running | streaming | validating_result |
            completed | failed | cancelled | expired
CalendarKind = gregory | islamic-umalqura | islamic-civil | unknown
DataClassification = public | internal | confidential | restricted
ResultFinality = preview | provisional | verified
EventDelivery = append | upsert | replace | tombstone
ActorKind = user | service | agent | external_agent | operator
```

## 3. Command envelope

Every product mutation is represented by `CommandEnvelope`:

```text
CommandEnvelope
  schema_version: Literal[1]
  command_id: UUIDv7                  # client generated for retry identity
  request_kind: RequestKind
  workspace_id: UUIDv7
  conversation_id: UUIDv7 | null
  parent_command_id: UUIDv7 | null
  idempotency_key: string[16..128]
  expected_revision: nonnegative int | null
  locale: BCP47                       # e.g. ar-SA, en-US
  timezone: IANA name
  requested_mode: auto | render_only | visual_transform | analyze | compose | revise
  requested_model_mode: auto | fast | balanced | deep
  payload: discriminated command payload
  client: {app_version, platform, session_id}
```

Server-derived fields (`tenant_id`, `user_id`, roles, policy, trace ID) are attached after authentication and MUST NOT be accepted from payload data.

Specialized mutation endpoints such as upload completion, cancellation, clarification answers, approval decisions, publication, and export accept their narrow endpoint schema; before changing state, the server constructs and persists the equivalent canonical `CommandEnvelope` with the fixed `request_kind`. They do not create an alternate mutation or idempotency path.

Idempotency behavior:

- same tenant + idempotency key + canonical command hash returns the original command/run result or current status;
- same key with a different hash returns `409 IDEMPOTENCY_CONFLICT`;
- the server stores the key and response pointer atomically before external work;
- retention is at least the maximum client retry/export/job window;
- downstream worker/export/publication calls derive stable child keys from the command ID and step name.

### 3.1 HTTP/SSE endpoint catalog

All endpoints are `/v1`, authenticated unless explicitly the liveness probe, return `ProblemDetails` on errors, and enforce request/response byte limits.

| Method/path | Purpose | Idempotency/concurrency |
|---|---|---|
| `POST /uploads` | create tenant-scoped upload and signed part URL | idempotency required |
| `POST /uploads/{id}/complete` | verify parts/hash, close upload, start scan/ingest | idempotency required; one terminal completion |
| `GET /uploads/{id}` | status | authorized read |
| `GET /datasets/{id}/versions/{version}` | dataset/profile metadata | authorized, paginated sections |
| `POST /commands` | submit any `CommandEnvelope` | idempotency required; expected revision when applicable |
| `GET /commands/{id}` | status/safe summary | authorized read |
| `GET /commands/{id}/events?after={cursor}` | SSE replay/live stream | cursor + heartbeat; no mutation |
| `POST /commands/{id}/cancel` | request cancellation | idempotency required |
| `POST /clarifications/{id}/answers` | answer and resume | idempotency required; first committed wins |
| `POST /approvals/{id}/decisions` | approve/deny/override | idempotency + actor/argument hash |
| `GET /artifacts/{id}` | latest authorized summary | authorized read |
| `GET /artifacts/{id}/revisions/{revision}` | immutable artifact envelope | ETag = spec/state hash |
| `GET /artifacts/{id}/data?cursor=` | paginated authorized source/result rows | signed cursor, size limit |
| `POST /artifacts/{id}/publish` | publish exact revision | idempotency + expected revision + authorization |
| `POST /artifacts/{id}/exports` | enqueue export | idempotency + exact revision |
| `GET /exports/{id}` | status/download grant | authorized read; short signed URL |
| `GET /catalog/models` | allowed modes/models/capabilities | user/workspace policy filtered |
| `GET /catalog/renderers` | allowed artifact/spec versions/limits | client-version filtered |
| `GET /health/live` | process liveness | no dependency detail |
| `GET /health/ready` | readiness | internal/ingress only; safe summary |

Pagination cursors bind tenant, user/policy version, resource, ordering, page size, and expiry. They are signed/opaque and cannot be reused for another resource.

## 4. Dataset and source contracts

```text
Dataset
  dataset_id, tenant_id, workspace_id
  display_name
  classification
  owner_user_id
  retention_policy_id
  created_at, deleted_at?

DatasetVersion
  dataset_version_id, dataset_id
  version_number
  original_object_id
  original_sha256
  canonical_object_id?
  canonical_sha256?
  canonical_format: parquet | arrow | none
  byte_size, row_count?, column_count?
  ingestion_status
  schema_profile_id?
  scan_status
  created_by, created_at

ColumnProfile
  column_id                         # stable within DatasetVersion
  source_name, display_name
  source_position
  physical_type, logical_type
  semantic_role: measure | dimension | time | geo | identifier | text | unknown
  nullable
  null_count?, distinct_count?
  min?, max?, quantiles?
  raw_examples[]                    # redacted/bounded
  unit?, currency?, timezone?, calendar?
  inference_confidence
  warnings[]

SourceView
  source_view_id, dataset_version_id
  ordered_column_ids[]
  row_selector: all | explicit_range | explicit_ids | approved_filter
  source_order_policy: preserve | explicit_sort
  operations[]                      # empty for exact mode
  data_mode
  ordered_value_sha256
  row_count
  schema_sha256
  created_by, created_at
```

`SourceView.data_mode=exact` requires `operations=[]`, `row_selector in {all, explicit_range, explicit_ids}` selected directly by the user, and `source_order_policy=preserve`. An `approved_filter` is transformed even when it only removes rows.

## 5. Request intents

```text
RenderIntent
  kind: Literal['render']
  source_view_id
  exact_lock: bool
  requested_artifact_kind
  requested_chart_family?
  bindings[]
  presentation?

TransformIntent
  kind: Literal['transform']
  source_view_id
  goal
  operations: TransformOperation[]
  output_name
  approval_token?

AnalyzeIntent
  kind: Literal['analyze']
  dataset_version_id | governed_source_id
  question
  analysis_plan?                    # absent until planned/approved

ComposeIntent
  kind: Literal['compose']
  artifact_revision_ids[]
  output_kind: dashboard | report | infographic
  audience?, layout_constraints?, global_filters[]

ReviseIntent
  kind: Literal['revise']
  artifact_id
  base_revision
  request_text? | direct_patch

UnlockExactIntent
  kind: Literal['unlock_exact']
  lock_scope_id                     # authoritative conversation/artifact lock record
  expected_lock_revision
  acknowledged_consequences: Literal[True]
```

An unlock is a separate authenticated, audited command. Supplying `exact_lock=false`, changing requested mode, or asking for a transform does not clear a persisted lock. A successful unlock increments the lock revision; the original transform/analyze request is then retried as a child command so its intent and idempotency record remain explicit.

## 6. Exact rendering and binding contract

```text
VisualBinding
  channel: x | y | color | size | shape | label | row | column | detail | latitude |
           longitude | geometry | time | tooltip | source | target | weight
  column_id
  scale_type?: linear | log | time | ordinal | band | identity
  aggregate: Literal['none']        # exact mode only
  display_format_id?

ExactRenderProof
  source_view_id
  source_ordered_value_sha256
  renderer_input_ordered_value_sha256
  source_row_count
  renderer_input_row_count
  operation_count: Literal[0]
  analysis_run_id: Literal[None]
  sample_policy: Literal['none']
  verified_at
```

Exact mode permits parsing needed to represent a value, but parsing MUST retain the raw token and MUST pass a declared round-trip equivalence rule. If not, the command moves to `input_required` with code `AMBIGUOUS_PARSE`.

Chart families requiring derivation—histogram, box plot, aggregate heatmap/choropleth, percent-of-total, density, regression/trend line, top-N, forecast—are illegal under exact mode. Scatter, line, area, raw bar/column, point map, raw route, table, and graph MAY be exact when each mark maps one-to-one to source records and no renderer transform is enabled.

## 7. Transform contract

Only these discriminated operations are allowed in release 1:

```text
FilterRows(column_id, operator, typed_value | typed_values)
SortRows([{column_id, direction, nulls}], stable=true)
SelectColumns(ordered_column_ids)
RenameColumn(column_id, display_name)                  # metadata only
CastColumn(column_id, target_type, parse_policy)
DeriveColumn(expression_ast, output_type, output_name) # allowlisted expression AST
BinColumn(column_id, strategy, count_or_edges)
Aggregate(group_by_ids, measures[])
Pivot(index_ids, column_id, value_ids, aggregate)
Unpivot(id_ids, value_ids, name_column, value_column)
Join(left_view, right_view, approved_relationship_id, join_type)
GeoProject(geometry_id, source_crs, target_crs='EPSG:4326')
SpatialJoin(left_geometry, right_boundary_version, predicate)
CalendarConvert(column_id, source_calendar, target_calendar, library_version)
SampleRows(method, count_or_fraction, seed, strata_ids[]?)
```

```text
TransformPlan
  schema_version, plan_id, parent_plan_id?
  source_view_id, source_version_hash
  operations: TransformOperation[]
  output_name, expected_schema[]
  approval_ids[]
  execution_budget
  actor/model provenance
  plan_sha256

TransformRun
  transform_run_id, plan_id
  status, attempt
  input_source_view_id, output_source_view_id?
  input_sha256, output_sha256?
  execution_report_id?
  started_at?, completed_at?
```

The expression AST supports literals, column references, arithmetic, comparison, boolean operators, `coalesce`, allowlisted string/date functions, and `case`. No function name, file path, URL, SQL fragment, code string, import, or attribute access is accepted.

`SampleRows` is deterministic: it records the method, exact count or fraction, seed, optional strata, source/result counts, and resulting ordered hashes; its output `data_mode` is `sampled`. Imputation is unsupported in release 1 and MUST fail with `INVALID_PLAN`; adding it requires a versioned operation contract and tests.

Every transform records input/output hashes, operation versions, row counts, null deltas, type changes, rejected rows, warnings, engine version, and execution budget. Preview approval is mandatory for joins without a pre-approved relationship, lossy casts, row removal above policy threshold, sampling, and operations affecting restricted data.

## 8. Analysis contract

```text
AnalysisPlan
  schema_version, plan_id, parent_plan_id?
  source_id, source_version_hash, semantic_model_version_id?
  intent_type: kpi | trend | comparison | distribution | relationship | geo | table | forecast
  question
  metrics[]: MetricRef | AdHocMeasure
  dimensions[]
  filters[]
  time_spec?
  joins[]
  statistic_spec?
  sort[]
  limit?
  other_policy: none | explicit_other
  output_grain[]
  expected_schema[]
  privacy_policy
  execution_budget
  clarification_resolutions[]
  model_provenance
  plan_sha256
```

`TimeSpec` contains field, canonical half-open range, source/display calendar, timezone, grain, comparison, incomplete-period policy, missing-period policy, fiscal policy, and conversion version.

`MetricRef` contains governed metric ID/version. `AdHocMeasure` contains input column, allowlisted aggregate, null policy, unit/currency, and a user-visible definition. Ratios require explicit numerator, denominator, zero policy, and scale. Growth requires ordered period, comparison basis, zero/negative-baseline policy, and partial-period policy.

`ExecutionBudget` contains deadline, max rows/bytes scanned, max result rows/bytes, max memory, max temp disk, max CPU seconds, and cancellation token ID.

## 9. Result and evidence contract

```text
ResultSet
  result_set_id, analysis_run_id
  schema[]
  grain[]
  row_count, byte_size
  object_id, content_sha256
  data_mode: transformed | aggregated | sampled
  finality
  validation_report_id
  warnings[]
  created_at

EvidenceRef
  evidence_id
  result_set_id
  row_key | cell_key | range_key
  value_sha256
  display_value
  unit?, currency?, calendar?, timezone?

Insight
  insight_id
  method_id, method_version
  statement_template_id
  evidence_refs[]
  baseline, effect_size, uncertainty?, sample_size?
  assumptions[], warnings[]
  verification_status
```

Narrative output represents numbers as evidence references during generation. The host substitutes approved localized display values after output validation. Free numeric tokens without evidence references fail validation.

## 10. Artifact envelope and renderer variants

```text
ArtifactEnvelope
  schema_version
  artifact_id, revision_id, revision_number, parent_revision_id?
  kind, status, data_mode
  title, description?
  source_view_id
  analysis_plan_id?, analysis_run_id?, result_set_id?
  exact_render_proof?
  renderer_variant
  renderer_spec_version
  renderer_spec
  presentation
  warnings[]
  created_by, created_at
  spec_sha256, data_sha256
```

Rules:

- exact artifact: `exact_render_proof` required and analysis/result IDs absent;
- analytical artifact: analysis/result IDs and verified result required for `final`;
- sampled artifact: sample method, seed, source/result counts, and visible badge required;
- map: boundary/source license and version, CRS, geometry/time metadata required;
- published artifact: immutable; editing creates a child draft revision;
- renderer spec is a discriminated allowlisted variant; raw executable callbacks/functions are forbidden.

## 11. Clarification and approval contracts

Clarification obtains missing information. Approval authorizes a fully specified consequential action. They are distinct.

```text
ClarificationRequest
  clarification_id, command_id, run_id?
  reason_code
  question_localized
  answer_schema                    # strict JSON Schema
  choices[]?                       # mutually exclusive, stable IDs
  default_choice_id?               # only if harmless/reversible
  consequences_by_choice
  requested_from: user_id | role | parent_agent
  expires_at
  status: pending | answered | expired | cancelled

ClarificationAnswer
  clarification_id
  answer_id
  answer_payload
  actor
  submitted_at
  idempotency_key

ApprovalRequest
  approval_id, command_id
  action_type
  validated_arguments
  argument_sha256
  effect_summary
  data/cost/risk summary
  requested_from
  expires_at
  status: pending | approved | denied | expired | cancelled

ApprovalDecision
  approval_id
  decision: approve | deny | approve_with_overrides
  overrides?                       # revalidated; creates new argument hash
  actor, decided_at, idempotency_key
```

The implementation uses Pydantic AI deferred calls for model-originated approval/external-result needs, while Postgres stores the product-authoritative request/decision. Client-supplied approval is never trusted by itself: the server authenticates the actor, reloads the pending request, verifies actor authority, expiry, status, and exact argument hash, then records one terminal decision.

Clarification rules:

- ask one grouped question containing at most three independently answerable fields when possible;
- never ask for information already present in authoritative state;
- never ask the model to infer an unanswered high-impact field;
- maximum two clarification rounds per command; a third unresolved ambiguity fails with `AMBIGUOUS_REQUEST` and actionable guidance;
- default timeout: 24 hours for interactive drafts, policy-configurable;
- answer after expiry returns `409 CLARIFICATION_EXPIRED` and offers a new command;
- multiple answers: first committed answer wins; exact duplicate is idempotent; conflicting answer returns `409 ALREADY_ANSWERED`;
- user cancellation transitions both clarification and command to cancelled;
- answers are untrusted inputs and revalidated before resuming.

External-agent flow:

1. external agent calls MCP command with its service identity and delegated user/workspace token;
2. service returns `input_required` plus `clarification_id`, safe question, answer schema, expiry, and resume token;
3. parent agent/host asks the authorized human or supplies known authoritative information;
4. parent calls `answer_clarification`; service authenticates and resumes the same command;
5. polling/subscription uses command ID; duplicate resumes are idempotent.

## 12. Command state machine

Allowed transitions only:

| Current | Trigger | Next | Required atomic writes |
|---|---|---|---|
| — | valid authenticated command | accepted | command + idempotency record + audit |
| accepted | validation begins | validating | status event |
| validating | missing material input | input_required | clarification + command status + outbox |
| validating | fully specified consequential action needs approval | approval_required | approval + command status + audit + outbox |
| validating | ready, synchronous | running | resolved intent/versions/budgets |
| validating | ready, background | queued | job + command status + outbox |
| input_required | valid answer | validating | answer + consumed marker + outbox |
| input_required | expiry | expired | terminal status + outbox |
| approval_required | valid approve/approve-with-overrides decision | validating | decision + consumed marker + audit + outbox |
| approval_required | deny decision | failed | decision + `APPROVAL_DENIED` + audit + outbox |
| approval_required | expiry | expired | approval/command terminal status + audit + outbox |
| queued | worker lease | running | attempt/lease + outbox |
| running | first artifact event | streaming | artifact draft + outbox |
| streaming | execution complete | validating_result | immutable result pointer + outbox |
| running | no-stream execution complete | validating_result | immutable result pointer + outbox |
| validating_result | all gates pass | completed | final artifact/revision + audit + outbox |
| nonterminal | authorized cancellation | cancelled | cancellation marker + outbox |
| nonterminal | terminal non-retryable error | failed | typed error + audit + outbox |
| running/streaming | retryable failure within budget | queued/running | attempt + classified error + outbox |

Terminal states are `completed`, `failed`, `cancelled`, `expired`. No transition leaves a terminal state. Retry creates another attempt inside the same command, not a new command. User “try again” creates a child command with a new ID.

## 13. Per-mode execution state machines

### 13.1 Exact render

```text
validate source access
→ validate exact SourceView and bindings
→ if incompatible chart: input_required
→ create preview artifact shell
→ emit schema/binding
→ stream exact ordered batches
→ compute renderer-input fingerprint
→ compare fingerprint + row count with source
→ validate renderer spec/a11y
→ finalize exact proof and artifact
```

Any fingerprint/count mismatch fails closed with `EXACTNESS_VIOLATION`; the preview is marked failed and cannot be published.

### 13.2 Transform/analyze

```text
validate source/semantic access
→ produce/validate typed plan
→ clarify/approve if required
→ freeze plan hash and budget
→ enqueue isolated execution
→ stream shell/status (never unverified claim)
→ execute immutable result
→ schema/grain/reconciliation/privacy validation
→ stream batches/provisional visual
→ insight verification
→ artifact/renderer/a11y validation
→ finalize
```

### 13.3 Revision

```text
load artifact + authorize + check expected_revision
→ classify presentation | binding | composition | transform | analytical
→ validate lock/mode boundary
→ presentation/binding/composition: patch + validate + new revision, no query
→ transform: child TransformPlan/TransformRun/SourceView + new revision
→ analytical: child AnalysisPlan/AnalysisRun/ResultSet + new revision
→ emit plain-language diff and lineage
```

## 14. Stream protocol

```text
StreamEvent
  schema_version: 1
  event_id: UUIDv7
  request_id, command_id, run_id?, conversation_id?
  artifact_id?, revision_id?
  sequence: positive int              # monotonic per command stream
  artifact_sequence?: positive int    # monotonic per artifact
  occurred_at
  event_type
  delivery: append | upsert | replace | tombstone
  payload
  payload_sha256
```

Event types:

- `run.accepted`, `run.status`, `run.input_required`, `run.approval_required`, `run.resumed`, `run.cancelled`, `run.failed`, `run.completed`;
- `intent.resolved`;
- `dataset.profile_patch`;
- `artifact.created`, `artifact.status`, `artifact.binding`, `artifact.spec_patch`, `artifact.finalized`, `artifact.failed`;
- `analysis.plan`, `result.schema`, `result.batch`, `result.reconciled`;
- `insight.verified`;
- `dashboard.widget_added`, `dashboard.layout_patch`;
- `approval.required`, `approval.resolved`.

Delivery rules:

- persist event/outbox before delivery;
- replay is exclusive after the caller's last acknowledged cursor and is idempotently reduced by `event_id`;
- duplicate delivery is legal; out-of-order sequence is buffered up to a limit, then snapshot recovery is requested;
- payload batches have bounded rows/bytes and checksums;
- reconnect endpoint returns snapshot + next cursor when event retention is exceeded;
- heartbeat contains cursor only and never advances artifact state;
- proxy buffering is disabled and tested;
- client disconnect cancels only work whose policy says `cancel_on_disconnect`; background/profile/export defaults to continue;
- final event is emitted only after state commit.

## 15. Revision and concurrency contract

- artifact revisions use optimistic concurrency with `expected_revision`;
- one branch may have multiple child drafts; publication identifies one exact revision;
- stale patch returns `409 REVISION_CONFLICT` with current revision and a safe rebase description;
- server auto-rebase is allowed only for commutative presentation fields changed on different paths;
- data/analysis/binding conflicts never auto-merge;
- undo creates a new revision copying a prior semantic state; history is not deleted;
- delete is tombstone + retention workflow; published/shared references show unavailable after policy deletion;
- style revision preserves data/result hash;
- binding revision preserves source/result hash and creates no analysis run;
- transform revision creates new transform-plan/run/source-view IDs;
- analytical revision creates new analysis-plan/run/result IDs.

## 16. Retry, timeout, and circuit-breaker matrix

| Layer | Timeout | Retries | Retryable | Never retry |
|---|---:|---:|---|---|
| browser command POST | 15 s response-to-accept | client 2 with same key | network/no response | validated 4xx |
| SSE connect | 15 s | exponential reconnect, max 5 min | disconnect/502/503 | auth/forbidden/schema mismatch |
| model transport | 30 s connect, step deadline by mode | 2 jittered within total budget | timeout, 429, selected 5xx | auth, policy, invalid request, safety refusal |
| model structured output | mode budget | 1 repair request | schema validation error | repeated invalid output |
| local tool | explicit per tool, max 30 s interactive | 1 model repair | validation/declared transient | policy, auth, unknown tool |
| MCP call | 20 s default | 1 if read-only/idempotent | transport/429/selected 5xx | side effect without idempotency, auth/policy |
| analysis job | plan deadline; default 120 s small upload | worker attempts 2 | worker crash/transient storage | invalid plan/data, budget, cancellation |
| export job | 180 s | 1 | browser crash/transient store | invalid spec/asset/security violation |
| DB transaction | 5 s | driver 2 serialization/deadlock | serialization/deadlock | constraint/auth/schema |
| object operation | 30 s | SDK 3 idempotent | timeout/selected 5xx | permission/hash mismatch |

One total deadline governs nested attempts. Retry/fallback counters and sleep time are observable. Model fallback uses only compatible policy-approved models and is not counted as a transport retry; at most one fallback per logical step. Logical model steps, application-level requests (initial, repair, and fallback), and provider transport attempts are separate counters and budgets.

## 17. Error catalog

All errors use:

```text
ProblemDetails
  type_uri, error_code, title_localized, safe_detail_localized
  http_status, request_id, trace_id
  retryable, retry_after_ms?, action?
  field_errors[]?
```

Required stable codes:

- authentication/authorization: `UNAUTHENTICATED`, `FORBIDDEN`, `TENANT_SCOPE_VIOLATION`;
- command/state: `INVALID_COMMAND`, `IDEMPOTENCY_CONFLICT`, `INVALID_TRANSITION`, `REVISION_CONFLICT`, `ALREADY_ANSWERED`, `CLARIFICATION_EXPIRED`, `APPROVAL_DENIED`, `APPROVAL_EXPIRED`;
- input/data: `UNSUPPORTED_FILE`, `FILE_TOO_LARGE`, `MALWARE_DETECTED`, `ENCODING_AMBIGUOUS`, `AMBIGUOUS_PARSE`, `AMBIGUOUS_REQUEST`, `UNSUPPORTED_CALENDAR_RANGE`, `INVALID_GEOMETRY`, `UNKNOWN_CRS`;
- exactness: `EXACT_MODE_CONFLICT`, `EXACTNESS_VIOLATION`, `RENDER_LIMIT_EXCEEDED`;
- planning/execution: `INVALID_PLAN`, `SEMANTIC_AMBIGUITY`, `QUERY_POLICY_DENIED`, `EXECUTION_BUDGET_EXCEEDED`, `RESULT_VALIDATION_FAILED`, `INSUFFICIENT_SAMPLE`;
- agent/provider/tool: `MODEL_UNAVAILABLE`, `MODEL_OUTPUT_INVALID`, `MODEL_POLICY_DENIED`, `TOOL_FAILED`, `MCP_UNAVAILABLE`, `RETRY_BUDGET_EXCEEDED`;
- renderer/export: `UNSUPPORTED_ARTIFACT_VERSION`, `INVALID_RENDERER_SPEC`, `RENDER_FAILED`, `EXPORT_FAILED`;
- system: `RATE_LIMITED`, `DEPENDENCY_UNAVAILABLE`, `INTERNAL_ERROR`, `CANCELLED`.

Provider stack traces, queries with sensitive literals, file paths, secrets, and raw data never enter client details.

## 18. Publication and export

Publication requires:

- final artifact revision;
- verified result or exact-render proof;
- no unresolved warnings classified blocking;
- authorization and workspace publication policy;
- immutable publish record with artifact, data, code/config/model/prompt/skill/renderer versions;
- access policy and optional expiry.

Exports require the same revision ID and include provenance metadata or a sidecar manifest. Draft export is allowed only with a visible `DRAFT / NOT VERIFIED` watermark. Export failure never changes the artifact's valid state.

## 19. Persistence mapping and constraints

Postgres tables, with UUIDv7 primary keys unless stated:

```text
tenants
users
workspaces
workspace_memberships
datasets
dataset_versions
source_views
semantic_model_versions
commands
command_attempts
clarifications
clarification_answers
approvals
approval_decisions
analysis_plans
analysis_runs
transform_plans
transform_runs
result_sets
evidence_refs
insights
artifacts
artifact_revisions
dashboard_dependencies
exports
publications
model_catalog_versions
prompt_skill_versions
audit_events
outbox_events
idempotency_records
```

Mandatory constraints:

- every tenant-owned table contains `tenant_id`; composite foreign keys include tenant ID so cross-tenant references are impossible at the database layer;
- unique `(tenant_id, workspace_id, idempotency_key)`;
- unique `(artifact_id, revision_number)` and exactly one parent per nonroot revision;
- at most one terminal clarification answer/approval decision enforced transactionally;
- command/artifact status check constraints and transition function reject illegal transitions;
- artifact exact/analytical consistency check enforced by deferred database constraint or finalization transaction;
- object/result hashes and schema versions nonnull before finalization;
- outbox sequence unique per command and artifact sequence unique per artifact;
- audit is append-only to application roles; corrections append a new event;
- soft deletion/tombstone is distinct from retention purge; purged object pointer cannot be reused.

Transactions:

- command accept: idempotency + command + audit + outbox;
- clarification/approval: terminal decision + command transition + audit + outbox;
- artifact revision: expected revision check + new immutable revision + audit + outbox;
- result finalization: result/validation pointers + artifact final state + audit + outbox;
- publication: authorization/policy snapshot + immutable publication + audit + outbox.

The outbox dispatcher uses leased batches, at-least-once delivery, attempt/dead-letter fields, and idempotent event IDs. A dead-letter event pages operations when it blocks user-visible terminal state.

## 20. Cache contract

Cache keys include tenant, workspace, policy version, data classification, dataset/source/semantic/plan/result version hashes, operation/engine version, locale only when output depends on locale, and caller visibility class. Cache entries contain source hashes and expiry; a mismatch is a miss, never a warning.

- exact source batches may cache only within the authorized workspace and source-view version;
- analytical results cache immutable verified `ResultSet`s, not provisional rows;
- authorization is rechecked before serving a hit;
- deletion/policy change publishes invalidation, while short TTL bounds missed invalidation;
- Redis loss yields misses and rate-limit degraded policy; it cannot lose authoritative work;
- negative authorization/existence responses are not shared across users/tenants.
