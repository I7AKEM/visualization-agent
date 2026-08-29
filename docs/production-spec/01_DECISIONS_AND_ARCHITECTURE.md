# Decisions and architecture

Normative language: **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are requirements levels. An implementation that violates MUST/MUST NOT is non-conforming.

## 1. Users and supported jobs

| Actor | Allowed jobs | Forbidden assumptions |
|---|---|---|
| Viewer | inspect published artifacts, filters, lineage allowed by policy, export if granted | cannot edit/query because a URL is known |
| Analyst | upload, bind, transform, analyze, revise, compose, publish within workspace permissions | cannot bypass semantic definitions or data policy |
| Data steward | confirm field semantics, quality rules, boundaries, metrics, retention | approval does not grant unrelated data access |
| Workspace admin | membership, approved models/connectors, quotas, publication policy | cannot read restricted content unless separately authorized |
| Platform operator | service health, deploy, rollback, redacted traces | telemetry access is not dataset access |
| External agent | narrow MCP operations under service identity/user delegation | cannot inherit the parent user's entire authority implicitly |

Primary jobs:

1. visualize chart-ready data exactly;
2. prepare data visibly for a requested visual;
3. ask and answer a verifiable analytical question;
4. explore alternatives without losing history;
5. revise appearance, bindings, or analysis with correct recomputation;
6. build a streaming dashboard/report/infographic;
7. create spatial and temporal views including Saudi/Hijri contexts;
8. publish/export a frozen artifact with provenance;
9. allow another authorized agent to request the same governed operations.

## 2. System invariants

Identifiers and isolation:

- every request MUST carry server-derived `tenant_id`, `workspace_id`, `user_id`, `request_id`, and `trace_id`;
- clients MAY send resource IDs but MUST NOT supply authoritative tenant/user identity;
- every database row, object key, cache key, event, workflow, and trace MUST be tenant/workspace scoped;
- authorization MUST run before lookup, before execution, and before returning cached or persisted data;
- a missing policy decision MUST deny access.

Data truth:

- the LLM MUST NOT calculate final numerical values used in artifacts;
- every numeric/temporal/geospatial claim MUST resolve to a verified result cell or typed evidence object;
- source, canonical, transformed, result, and rendered data hashes MUST be distinct named fields;
- `data_mode` MUST truthfully be `exact`, `transformed`, `aggregated`, or `sampled`;
- unsupported/ambiguous semantics MUST produce `input_required` or a typed refusal—not a guess.

Execution:

- arbitrary model-generated Python, JavaScript, React, HTML, shell, SQL, and map expressions MUST NOT execute in normal product flows;
- all operations MUST be selected from typed allowlisted operators and renderer components;
- external SQL MUST be read-only, parsed/policy-checked, dry-run, bounded, isolated, and audited;
- retries MUST be bounded, classified by layer, and allowed only when safe;
- every side effect MUST have an idempotency key.

User experience:

- the first visual shell MUST stream before narrative completion;
- preview/provisional/final MUST be visually and semantically distinct;
- cancellation, reconnect, and resume MUST preserve valid completed work;
- direct deterministic UI edits MUST NOT call an LLM;
- an exact-render lock MUST persist until explicitly unlocked by the user.

## 3. Mode resolution decision table

Precedence is first matching rule from top to bottom.

| Priority | Condition | Resolved intent | Clarification |
|---:|---|---|---|
| 1 | authenticated user lacks dataset/artifact permission | reject `forbidden` | never ask for data details |
| 2 | explicit `render_only_lock=true` and requested operation changes values/order/row set | `input_required` | explain conflicting operation; offer unlock or cancel |
| 3 | UI supplies chart type, valid field bindings, source view, and no transform | `render_only` | none |
| 4 | user explicitly says “as-is/exact/no calculation/no transformation” | `render_only` | ask only if chart itself requires computation |
| 5 | request changes only style/layout/labels/camera/animation | `revise.presentation` | none |
| 6 | request rebinds existing fields or composes existing artifacts without changing data | `revise.binding_or_composition` | none when bindings validate |
| 7 | request names filter/sort/bin/pivot/reshape/calculated field/normalization | `visual_transform` | only for ambiguous operands or semantic consequences |
| 8 | request names aggregate/KPI/share/growth/rank/comparison/join/statistic/forecast/insight | `analyze` | for metric, unit, denominator, join, period, or method ambiguity |
| 9 | request builds dashboard/report from existing artifacts | `compose` | ask for audience/layout only if necessary; use defaults otherwise |
| 10 | natural language remains ambiguous after deterministic rules | classifier | classifier returns intent + confidence + missing fields, never execution |
| 11 | classifier confidence below configured threshold or multiple material interpretations | `input_required` | present mutually exclusive interpretations |

The classifier sees request text, UI state, dataset schema/profile IDs, and existing artifact summary. It MUST NOT see complete raw datasets. Classification is limited to one model request, no tools, temperature 0 or provider-equivalent deterministic settings, and a strict typed output.

## 4. Component topology and ownership

```text
Browser
  ├─ chat/input/clarification UI
  ├─ source-data view and binding controls
  ├─ authoritative server-state reducer + optimistic local actions
  └─ renderer registry
       GPT-Vis/G2 | S2 | Mapbox/react-map-gl/deck.gl | G6 | Infographic | React widgets
            │
            │ HTTPS + SSE, resume cursor, CSRF/origin controls
            ▼
API service
  ├─ authentication/session and authorization policy
  ├─ command validation/idempotency/concurrency
  ├─ mode router and state machine
  ├─ direct-binding/artifact service
  ├─ Pydantic AI planner/advisor/narrator
  ├─ clarification/deferred-call coordinator
  ├─ revision/publish/export service
  └─ transactional state + outbox
            │
            ├─ analysis queue → isolated analysis worker → object/result store
            ├─ export queue → isolated export worker → object store
            ├─ optional governed semantic/query providers
            ├─ optional MCP clients/first-party MCP facade
            └─ Logfire/OTel via collector
```

### 4.1 Browser responsibilities

The browser MUST:

- render only validated artifact variants registered in the shipped catalog;
- reduce ordered server events by `artifact_id` and sequence;
- persist no provider/database secrets;
- send commands, not self-authored state snapshots;
- sanitize all rich text, tooltips, labels, URLs, SVG, and exported markup;
- use virtualized tables and renderer-specific size limits;
- preserve keyboard, screen-reader, reduced-motion, RTL/LTR, locale, and high-contrast behavior;
- show exact/transformed/aggregated/sampled status and source lineage;
- stop optimistic state when the server rejects a stale revision.

The browser MUST NOT:

- decide authorization, approval validity, final analytical status, or data exactness;
- execute agent-generated code;
- submit complete authoritative message history as trusted server state;
- embed secret Mapbox tokens or unrestricted public tokens.

### 4.2 API responsibilities

The API is the authoritative host. It MUST:

- validate all commands with strict Pydantic models;
- derive identity and policy, acquire idempotency/concurrency controls, and load server-owned state;
- resolve intent and run only the legal state transition;
- persist state and outbox event atomically;
- stream events from committed outbox/order, not transient in-process assumptions;
- call the model only through the approved catalog and usage policy;
- redact provider/internal errors into stable product errors;
- propagate deadlines/cancellation/correlation IDs;
- verify worker results before finalizing an artifact.

### 4.3 Analysis worker responsibilities

The worker MUST:

- accept immutable dataset/source/plan IDs rather than raw client paths;
- run one tenant job in an isolated process/container with CPU, memory, disk, row, byte, and wall-clock limits;
- have no outbound network unless an approved connector job explicitly needs one;
- load only preinstalled allowlisted DuckDB extensions;
- compile typed operations; generated code is prohibited;
- write results to a new immutable object then return its hash/schema/statistics;
- be idempotent for `(tenant_id, plan_hash, dataset_version_hash, engine_version)`;
- handle cancellation and delete temporary files through a tenant-safe cleanup job.

### 4.4 Export worker responsibilities

The export worker MUST:

- consume only finalized or explicitly watermarked draft artifact versions;
- use the same renderer/spec validation and fonts as the browser;
- block external network except allowlisted asset fetches proxied/scanned by the API;
- sanitize SVG/HTML and enforce page/image/time/memory limits;
- record renderer/browser/font versions and output hash;
- never send data to AntV's public service.

### 4.5 Agent responsibilities

Use separate logical agents/functions with narrow outputs; they MAY share an approved model but MUST have distinct prompts, tools, budgets, and eval slices.

| Logical component | Input | Output | Tools | Max logical model steps |
|---|---|---|---|---:|
| Intent classifier | request + compact state | `IntentDecision` | none | 1 |
| Visualization advisor | profile + user goal + retrieved reviewed chart context | `VisualizationProposal[]` | chart-context retrieval only | 2 |
| Transform planner | schema/profile + explicit requested transform | `TransformPlan` | semantic/profile lookup | 2 |
| Analysis planner | schema/semantic model + question | `AnalysisPlan` or `ClarificationRequest` | semantic/profile lookup | 3 |
| Revision classifier | artifact summary + revision text | typed revision command or clarification | artifact metadata only | 1 |
| Insight narrator | verified results/insights only | grounded narrative with evidence refs | evidence lookup | 2 |
| Dashboard composer | existing artifact summaries | `DashboardSpec` | artifact catalog lookup | 2 |

One logical model step may use the bounded transport attempts, one structured-output repair, and one compatible fallback allowed by `02_CONTRACTS_AND_STATE_MACHINES.md`. Logical steps, application-level requests, and provider transport attempts are counted separately in traces/evals and all remain inside the step and run budgets.

No logical agent has shell, arbitrary HTTP, filesystem, raw database, object-storage, renderer execution, publication, or deletion authority.

### 4.6 Model-visible tool catalog

These are the only release-1 tools visible to logical agents. Every call reauthorizes the run context. Results are bounded/redacted Pydantic models.

| Tool | Allowed agent | Input/result | Timeout/retry | Side effect/approval |
|---|---|---|---|---|
| `get_dataset_profile` | advisor, transform/analysis planner | dataset version ID + requested profile sections → schema/statistics/warnings, no full rows | 3 s / one idempotent retry | none/no approval |
| `get_semantic_context` | analysis planner | governed source + requested metric/dimension names → authorized definitions/relationships | 5 s / one retry | none/no approval |
| `get_artifact_summary` | revision/composer/narrator | artifact revision ID → kind, bindings, lineage, status, warnings | 3 s / one retry | none/no approval |
| `get_evidence` | narrator | evidence IDs, maximum 50 → verified display values/metadata | 3 s / one retry | none/no approval |
| `retrieve_chart_context` | advisor | sanitized query + library + topK≤7 → reviewed AntV context IDs/content | 5 s / one retry | none/no approval |
| `validate_plan_candidate` | transform/analysis planner | candidate typed plan → deterministic errors/warnings only | 3 s / none | none/no approval |
| `validate_visual_candidate` | advisor/composer/revision | candidate renderer variant → deterministic compatibility/errors | 3 s / none | none/no approval |

Agents do not directly execute plans. After structured agent output returns, ordinary application code validates and, if legal, enqueues execution. This prevents a model tool loop from performing data work.

Tools return stable error classes: `not_found` without cross-tenant existence detail, `forbidden`, `invalid`, `unavailable`, or `budget_exceeded`. Tool descriptions contain no secrets or internal table/path names.

## 5. Data storage ownership

| Store | Authoritative records | Never store |
|---|---|---|
| Postgres | tenants/users/workspaces, datasets and versions, source views, plans/runs, artifacts/revisions, commands, clarifications, approvals, audit, event outbox, model/prompt/skill catalog | full source/result blobs, secrets in plaintext |
| Object storage | original uploads, canonical Parquet/Arrow, immutable result batches, boundary/tile assets, exports, evidence reports | executable uploads served with active content types |
| Redis | rate limits, short leases, ephemeral cache, event fan-out hints | sole copy of conversation, artifact, approval, or job state |
| Durable engine DB | workflow/checkpoint state and idempotent step results | large raw datasets or unversioned Python objects |
| Logfire/OTel | redacted spans, metrics, logs, evaluation events | raw files, secrets, unrestricted row values, auth headers |

All object records include content hash, size, media type, encryption/key reference, tenant/workspace, creator, created time, retention class, scan status, schema version, and tombstone state.

## 6. Data classification and model egress

| Class | Example | External model | Telemetry content | Export/share |
|---|---|---|---|---|
| Public | published open dataset | approved providers | redacted samples allowed in non-prod only | allowed by workspace policy |
| Internal | ordinary business data | approved enterprise/no-training route with minimized context | IDs/schema/stats; no rows by default | authenticated only |
| Confidential | commercial/operational sensitive | private route or explicit policy-approved provider; no raw rows | hashes/IDs/aggregates | restricted, watermarked/audited |
| Restricted | PII, health, security-sensitive, regulated | private/local route only; field-level minimization | content capture off | denied unless policy and approval |

The profiler proposes classification; policy and steward confirmation determine it. A model switch MUST NOT change egress eligibility.

## 7. Renderer selection rules

| Need | Renderer | Constraints |
|---|---|---|
| common incremental chart | GPT-Vis | validated supported JSON/vis syntax; fallback to G2 |
| advanced grammar/custom interaction | G2/Ant Design Charts | typed adapter; no arbitrary function expressions |
| semantic common-chart compiler | not used in release 1; post-release Flint evaluation | must not change the stable artifact envelope or block the AntV implementation |
| analytical table | Ant Design Table/ProTable | pagination/virtualization and row limits |
| pivot/crosstab | S2 | preverified aggregates; virtualization; no hidden metric authority |
| geographic | Mapbox through react-map-gl | controlled state, licensed sources, URL-restricted token |
| large/animated spatial overlay | lazy deck.gl | only after data/precision/GPU budget validation |
| relationship graph | G6/Graphin | lazy load, node/edge limits, deterministic layout seed where possible |
| infographic | AntV Infographic | reviewed templates, finalized evidence, private export |
| KPI/custom visual | registered React component | fixed props schema, design tokens, reduced-motion alternative |

Unknown artifact/renderer/schema versions MUST render a safe “unsupported artifact version” state and MUST NOT attempt best-effort code execution.

## 8. Calendar and geography decisions

- canonical instants: UTC plus source IANA time zone;
- canonical date-only: ISO Gregorian `date` with no time-zone conversion;
- supported calendar tags: `gregory`, `islamic-umalqura`, `islamic-civil`, `unknown`;
- backend Umm al-Qura authority: pinned `hijridate` within documented 1343–1500 AH range;
- display: locale/`Intl`, never analytical authority;
- default Saudi workspace zone: `Asia/Riyadh`, only when workspace configuration says so;
- canonical geometry: valid WGS84 GeoJSON/OGC geometry with `[longitude, latitude]` order;
- spatial computation: isolated DuckDB Spatial worker, never render-only;
- boundary join: stable licensed boundary IDs, never display-name-only matching.

## 9. External interoperability

MCP:

- use MCP clients only for independently deployed external tools/data where interoperability is valuable;
- each server has an owner, auth method, allowed tools, input/output schemas, timeout, retry, quota, data classification, region, audit, health check, and disable switch;
- a first-party MCP facade MAY expose narrow application commands after the UI path is stable;
- MCP output is untrusted and revalidated; MCP does not bypass application authorization.

Agent-to-agent:

- no A2A dependency in the first release;
- an external agent calls first-party MCP tools and receives typed `completed`, `input_required`, `pending`, or `failed` results;
- the parent agent/host owns user clarification and returns correlated answers;
- add A2A only through an ADR when independent discovery/delegation and multi-turn remote sessions are required.

## 10. User-interface information architecture

Primary route: `/workspaces/{workspace_id}/visualizations/{conversation_or_artifact_id}`.

Desktop layout:

- left rail: workspace, datasets, saved artifacts, reports, recent branches;
- center: ordered conversation/data thread and live artifact canvas;
- right inspector: Data, Bindings, Style, Analysis, Lineage, Warnings, Accessibility tabs;
- top bar: dataset/source view, exact lock, resolved mode, model mode/model, connection/run status, publish/export;
- bottom or inline run strip: stage, cancel, clarification/approval, trace-safe run details.

Mobile/tablet collapses rails into drawers; the artifact remains primary and chat/inspector never cover critical clarification actions.

Required UI states:

- no dataset; uploading/scanning/profiling; profile ambiguity;
- ready exact binding; exact lock conflict;
- agent planning; input required; approval required; queued/running/streaming/validating;
- preview/provisional/final; warning; partial widget failure; cancelled; recoverable/nonrecoverable error;
- offline/reconnecting/replaying/snapshot recovered;
- stale revision/conflict; unsupported artifact version; access revoked/deleted.

Defaults that do not require clarification:

- locale/workspace theme and approved brand tokens;
- accessible palette, legend/tooltip, responsive sizing, reduced-motion preference;
- stable source order in exact mode;
- chart title generated from field display names and user wording, editable without model;
- `auto` model mode resolved server-side; selected concrete model remains visible in run details;
- empty narrative omitted rather than filled with generic text.

The UI asks only consequential questions defined by `ClarificationRequest`. Free-form assistant text cannot masquerade as a required form/approval.
