# Code test and failure matrix

## 1. Quality objective

Testing proves specified behavior; it does not prove the absence of every possible defect. Coverage is defined by:

1. every MUST/MUST NOT requirement mapped to at least one test ID;
2. every state transition tested for success, rejection, duplicate, timeout, cancellation, and unauthorized actor where applicable;
3. every supported equivalence class tested at representative, minimum, maximum, just-below, and just-above boundaries;
4. every invariant exercised by property and mutation tests;
5. every dependency boundary tested for malformed, slow, unavailable, duplicate, and inconsistent behavior;
6. risk-based pairwise coverage across browser × locale × mode × renderer × model × data size, plus three-way coverage for security/correctness combinations;
7. production incidents become permanent regression tests before the fix is released.

The requirements traceability table (`tests/requirements.yaml`) is mandatory. CI fails when a normative requirement has no test or a test references an unknown requirement.

### 1.1 Cross-cutting `LOCAL-RUNTIME` acceptance gate

A package that owns runnable behavior MUST pass `LOCAL-RUNTIME`; static analysis, unit tests, schema checks, and builds are necessary but are not acceptance substitutes. The gate is progressive across the integrated slice available to the package:

1. Install and start every relevant API, worker, and web application locally from frozen locks using repository-local or temporary toolchains. Verify liveness, readiness, dependency-failure behavior, and graceful shutdown without production access or data.
2. Exercise the agent through the real local API and streaming event path. Ordinary runs MUST use Pydantic AI `TestModel`, `FunctionModel`, or versioned recorded fixtures with live model requests disabled. A live paid-provider run requires separate explicit authorization and is never implied by this gate.
3. Starting with WP-05, run Playwright and use a real browser or Computer Use to click through the integrated UI. Cover upload, streaming, render, clarification/revision, reconnect, error, Arabic/RTL, keyboard/accessibility, and responsive paths as those behaviors enter the integrated slice.
4. WP-08 renderer, WP-09 map/temporal, WP-12 export/infographic, and later packages MUST extend the same local end-to-end suite rather than replace it with package-local static or component evidence.
5. Store exact start/test/shutdown commands; tool and lock versions; exit codes; health/readiness output; request, response, and ordered event traces; logs; screenshots or videos; dataset, result, and artifact hashes; failures; and retest results under `docs/evidence/<wp-id>/`.

Each subgate is recorded as `passed`, `failed`, or `not_applicable`. `not_applicable` requires an exact ownership/dependency explanation and cannot be used for runnable behavior the package owns. An integration record MUST NOT accept or conditionally accept a package when an applicable subgate lacks evidence or fails, and MUST preserve typed disabled behavior for owner-dependent capabilities.

## 2. Required test toolchain

Python:

- `pytest`, `pytest-anyio`, `pytest-cov`;
- `hypothesis` for property/stateful/model-based tests;
- Pydantic AI `TestModel`, `FunctionModel`, `Agent.override`, and global `ALLOW_MODEL_REQUESTS=False` for normal tests;
- `schemathesis` against generated OpenAPI;
- `testcontainers` for Postgres/Redis/object-store/DBOS integration;
- `mutmut` on contract validators, policy, exactness, reconciliation, and revision classification;
- `ruff`, `mypy --strict`, `bandit`, `pip-audit`.

TypeScript/UI:

- `tsc --noEmit` with strict settings;
- `eslint`;
- `vitest`, React Testing Library, `fast-check`;
- Playwright for E2E, visual snapshots, reconnect, multi-tab concurrency, RTL, and browser matrix;
- `axe-core`/Playwright accessibility checks;
- `npm audit` plus OSV/lockfile scan.

System:

- k6 for HTTP/SSE/load/soak;
- Toxiproxy for latency, packet loss, disconnect, and dependency faults;
- Trivy for images/SBOM/misconfiguration;
- OWASP ZAP baseline plus authenticated API tests;
- deterministic fixture/export comparison with perceptual pixel diff and semantic DOM/canvas assertions.

Versions are pinned. Adding a test tool requires supply-chain review.

## 3. Test layers and ownership

| Layer | Runs | External model/network | Gate |
|---|---|---|---|
| static/type/schema | every commit | none | zero errors |
| unit | every commit | prohibited | all pass |
| property/stateful | every commit for core; extended nightly | prohibited | all properties pass with saved failing seeds |
| mutation | nightly/release | prohibited | critical modules 100% mutation score; overall threshold recorded after baseline |
| contract/OpenAPI/event | every commit | none | all producer/consumer versions compatible |
| component/render | every commit | none | all pass; approved snapshots only |
| integration | PR/main | emulated/fake providers | all pass |
| E2E | PR/main/staging | fake model on PR; approved live models on staging | critical journeys all pass |
| security | PR/nightly/release | isolated | zero critical/high; reviewed medium |
| performance/load | nightly/release | approved test providers | SLO gates |
| chaos/recovery | nightly/release | production-like | all recovery invariants pass |
| offline agent eval | PR subset; full before release | approved live models | `04_AGENT_EVAL_SPEC.md` |
| online eval | staging/prod sampled | live | alert/rollback gates |

## 4. Contract and validation cases

### 4.1 Universal scalar/serialization cases (`CON-*`)

- valid and invalid UUIDv7; UUID from another tenant; malformed, empty, uppercase, overlong IDs;
- RFC 3339 valid UTC; offset input rejected at canonical boundary; missing zone; leap second policy; invalid date/time;
- integer boundary, negative where nonnegative, overflow, float supplied to integer, numeric string coercion rejected;
- decimal precision/scale, negative zero, NaN, infinity, exponent forms, localized separators;
- Unicode normalization NFC/NFD, bidi controls, zero-width characters, emoji, Arabic/Latin mixed labels, maximum lengths;
- empty/missing/null distinction for every optional/required field;
- unknown enum/discriminator, extra field, duplicate JSON key, deeply nested payload, cyclic client object impossible in JSON;
- current/previous schema version, future version, incompatible persisted payload, generated Python↔TypeScript round trip;
- canonical hash stable across key ordering and transport; one-byte change changes hash.

### 4.2 Command cases (`CMD-*`)

- each command payload under correct/wrong discriminator;
- trusted identity fields injected in payload are rejected/ignored and never override server identity;
- same idempotency key/same body before, during, and after completion;
- same key/different body conflict;
- missing/expired session, wrong workspace, deleted resource, stale revision;
- size limit exactly at/over boundary; rate limit and retry-after;
- cancel before accept, queued, running, streaming, validation, after terminal;
- child command references allowed/forbidden parent.

## 5. Authentication, authorization, and tenant isolation (`AUTH-*`)

For every read/mutation/export/MCP operation test:

- owner, allowed collaborator, viewer, workspace admin without content privilege, tenant admin policy, external agent, anonymous, expired/revoked identity;
- resource in same workspace, other workspace same tenant, other tenant, deleted/tombstoned, guessed UUID;
- direct request, cache hit, background job, replayed event, export URL, object URL, MCP path;
- role changed during long job; membership revoked before result delivery; publication policy changed during export;
- cache poisoning with identical source/query hash across tenants;
- server ignores client-supplied tenant/user/role/history/approval fields;
- row/column policy applied before plan and rechecked before execution/result/cache;
- signed URL scope, object key traversal, expiry, replay, content disposition/type.

Release gate: zero cross-tenant bytes, metadata, timing-derived existence disclosure beyond the approved generic response, or trace leakage.

## 6. Ingestion and profiling (`ING-*`)

Formats:

- CSV/TSV: UTF-8/UTF-8 BOM/approved legacy encoding, comma/tab/semicolon, quoted delimiter/newline/quote, CRLF/LF, blank lines, comments policy, duplicate/blank headers, ragged rows, huge fields;
- Excel: XLSX multiple sheets, formulas, cached values, hidden sheets/rows, merged cells, date serial systems, macros rejected, external links rejected, password-protected response;
- JSON: records/array, NDJSON if supported, nested object rejection/flatten policy, duplicate keys, enormous nesting;
- Parquet: valid, corrupt footer, nested unsupported type, multiple row groups, compression, malicious metadata size;
- compression: approved single archive if supported, zip bomb, path traversal, nested archive, decompression ratio/size limits;
- MIME/extension disagreement, polyglot, executable rename, empty file, zero rows, zero columns, one row/column, max allowed size/rows/columns;
- interrupted multipart/signed upload, checksum mismatch, duplicate upload, scan pending/failed/malware.

Values/types:

- null tokens versus literal strings, booleans, integers, decimals, scientific notation, thousands/decimal separators, SAR/halala, percent/fraction;
- Arabic-Indic/Eastern Arabic/Western digits, minus signs, currency symbols, whitespace, bidi marks;
- leading zeros/IDs, 64-bit boundaries, decimal precision, NaN/infinity, mixed type, sparse columns;
- dates in ISO, locale ambiguous, date-only, timestamp with/without zone, Excel serial, Hijri patterns, invalid calendar days;
- stable row IDs/order and raw-token preservation;
- profiling redaction for PII/secrets/prompt injection;
- deterministic profile/hash across repeated ingest and worker count.

Failure expectations: immutable original retained or safely rejected, partial canonical object never published, temporary data cleaned, typed error, audit event, no model call.

## 7. Router and modes (`MODE-*`)

Test every row in the mode decision table plus:

- explicit UI mode versus contradictory text;
- exact lock persisted across turns, reconnect, revision, model switch, copied artifact;
- `exact_lock=false` or a conflicting request cannot unlock; only a valid audited `unlock_exact` command with the expected lock revision succeeds, and stale/unauthorized unlocks fail;
- render request that requires histogram/bin, aggregate choropleth, box plot, share, trend line, forecast;
- style-only, binding-only, transform, analytical, composition examples in Arabic and English;
- classifier confidence at, below, and above threshold; conflicting interpretations; invalid classifier output; provider failure;
- no LLM call when deterministic rule resolves intent;
- maximum one classifier request, zero tools, correct context minimization;
- unsupported operation fails/clarifies instead of falling through to analysis.

Properties:

- `exact_lock=true` implies no legal transition to transform/analyze without an accepted unlock command;
- adding irrelevant wording cannot change a deterministic UI-selected mode;
- unauthorized data never reaches classifier context.

## 8. Exact rendering (`EXACT-*`)

For every supported exact renderer/chart family:

- 0/1/2/maximum rows; nulls; duplicate rows; duplicate x; unsorted time; negative/zero/large decimals; categorical high cardinality;
- row order preserved through batching, retry, reconnect, renderer reduction;
- raw and renderer input counts/hashes match;
- no transform/analysis job, SQL, tool, or model call in direct UI path;
- labels/format/localization do not alter data value/hash;
- renderer implicit transforms disabled;
- exact point map/route preserves coordinates/timestamps;
- chart limit overage offers declared alternatives without silently sampling;
- batch duplicated, omitted, reordered, corrupted checksum, stale artifact sequence;
- browser crash/reconnect and another tab resume;
- publish blocked when exact proof absent/mismatched.

Metamorphic properties:

- splitting the same ordered rows into different batch sizes yields identical final hash/artifact;
- changing palette/title/legend/animation yields identical data hash;
- identity parse/serialize yields the same canonical typed values and raw-token association;
- duplicating a row adds exactly one mark/row where the chosen exact renderer maps one-to-one.

## 9. Transform operations (`TRN-*`)

For each allowlisted operation test valid, empty, null, type mismatch, boundary, high cardinality, budget overrun, and deterministic repeat.

- filter: all operators/types, null semantics, locale/date/calendar values, zero/all rows, injection-looking values;
- stable sort: equal keys, null first/last, multi-key, ascending/descending, locale collation policy;
- select/rename: duplicate/missing IDs, reserved/Unicode names, order;
- cast: lossless/lossy, overflow, invalid rows, date/calendar range, explicit reject/null/error policies;
- derive AST: every operator/function, precedence, type checking, divide by zero, null propagation, depth/node limit; reject code/function/attribute/import/URL/path/SQL;
- bin: exact edges, equal values, negative range, empty bins, boundary inclusion;
- aggregate: each allowlisted aggregate, null/distinct semantics, decimal precision, grouping nulls, empty input;
- pivot/unpivot: duplicate keys, aggregate required, column explosion limit, reversible cases;
- join: one-to-one/one-to-many/many-to-many rejection/approval, null keys, duplicate keys, cross-tenant IDs, row explosion budget;
- geo projection/spatial join: CRS, invalid geometry, edge boundary, antimeridian;
- calendar conversion: valid/invalid/out-of-range, round trips, 29/30-day boundaries.
- sample: method/count/fraction/seed/strata validation, deterministic repeat, source/result counts and ordered hashes, approval, and visible `sampled` mode; imputation rejects as `INVALID_PLAN` in release 1.

Differential checks compare expected golden tables and a separately implemented simple reference for critical aggregates/ratios.

## 10. Analysis and numerical truth (`ANA-*`)

Plan:

- every plan union; required/forbidden fields by kind; unknown metrics/dimensions; illegal join; wrong output grain;
- metric version, units/currency, numerator/denominator, distinct/null policy;
- top-N ties, deterministic tie-break, explicit `Other`, negative values;
- time grains/ranges/comparisons, missing/incomplete periods, zero/negative growth baseline;
- empty result, one-row result, insufficient sample, divide by zero;
- budget accepted/rejected; malicious prompt/column name never becomes operation/code;
- model invalid output then one repair; second invalid fails;
- planner asks consequential clarification and does not ask known information.

Execution/validation:

- exact golden KPI/sum/mean/min/max/count/distinct/ratio/share/growth/rank/distribution;
- decimal precision and currency conversion prohibited unless an approved rate source exists;
- schema/grain/uniqueness mismatch, duplicate keys, null threshold, row/byte limit;
- total/subtotal/top-N/Other reconciliation;
- query cancellation at compile, scan, materialize, upload;
- worker memory/disk/time/CPU exhaustion;
- independent re-run deterministic hash for deterministic plans;
- cache correct/stale/wrong-version/tenant-safe;
- unsupported claim/evidence mismatch prevents finalization.

## 11. Calendar and time (`TIME-*`)

- Gregorian date, timestamp, offset, DST zones, `Asia/Riyadh`, date-only no-zone behavior;
- `islamic-umalqura` every supported year boundary plus first/last supported date;
- just outside 1343–1500 AH backend range fails explicitly;
- `islamic-civil` is never silently treated as Umm al-Qura;
- ambiguous “Hijri” requests clarification;
- 29/30-day months, leap cases, Ramadan/Dhul-Hijjah, Hijri/Gregorian year crossover;
- canonical half-open filter boundaries and round-trip fixture comparisons;
- Arabic/English month names, digit systems, RTL axes/tooltips, dual-calendar labels;
- browser `Intl` difference cannot alter backend result;
- incomplete current period, fiscal/week start, missing periods;
- event time, valid time, recorded time independently filtered.

Fixture provenance and conversion library/data versions are asserted in every case.

## 12. Geospatial-temporal (`GEO-*`)

- point/line/polygon/multipolygon/route, empty geometry, invalid/self-intersecting, holes, collections policy;
- longitude/latitude swapped detection, bounds ±180/±90, antimeridian, poles, precision;
- WGS84 and approved source CRS conversion; unknown/mislabeled CRS;
- stable Saudi region ID joins with Arabic/English names and spelling variants;
- boundary version changes and valid_from/valid_to;
- point-in-polygon on edge/hole, spatial join duplicates, distance units/projection warning;
- small GeoJSON batches, large vector-tile/viewport query, pan/zoom race, stale tile;
- live `setData`, duplicate/out-of-order features, timeline scrub, play/pause/speed;
- deck.gl timestamp normalization/float precision, out-of-order/missing route timestamps;
- Mapbox token missing/expired/restricted/rate-limited; no secret token in browser;
- privacy rounding, minimum aggregation threshold, sensitive-location denial;
- offline/no-basemap fallback preserves data layer status without fabricated geography.

## 13. Renderer/component registry (`VIS-*`)

For every registered component and spec version:

- minimal/typical/max valid spec; every invalid required field/channel/type;
- unknown component/spec/version/prop; extra prop; prototype pollution keys;
- malicious label/tooltip/URL/SVG/HTML; CSP and Trusted Types where used;
- zero/one/many series, nulls, long labels, Arabic/English/mixed bidi, emojis;
- responsive widths, mobile/tablet/desktop, print/export sizes, high DPI;
- light/dark/high-contrast, brand tokens, reduced motion;
- keyboard navigation, focus order, screen-reader name/summary, color contrast, non-color encoding;
- animation start/update/cancel and reduced-motion deterministic alternative;
- renderer exception isolated to its widget; other dashboard widgets continue;
- lazy bundle failure/retry; hydration/SSR boundary;
- semantic snapshot plus visual snapshot across Chromium/Firefox/WebKit supported versions;
- browser versus private-export visual/data/spec hash correspondence.

AntV skills are tested as context inputs: pinned version, retrieved IDs, conflicting/untrusted content, oversized retrieval, wrong library version, and product-rule precedence.

## 14. Streaming/reconnect (`STR-*`)

- every event type and legal order;
- duplicate, gap, reordering, corruption, unknown version/type, huge payload, heartbeat;
- reconnect before first event, mid-batch, after final, after retention expiry;
- snapshot + cursor convergence equals uninterrupted reduction;
- proxy buffering, slow client, backpressure, multiple subscribers, mobile network switch;
- cancellation propagation and policy-specific continue-on-disconnect;
- one widget failure does not terminate dashboard stream;
- preview/provisional/final status cannot regress;
- no final event before committed final state;
- Arabic localized status and stable error codes;
- SSE injection/newline framing and content-type/cache headers.

Property: reducing any delivery containing legal duplicates in any allowed delivery grouping produces the same final state as exactly-once ordered delivery.

## 15. Clarification, approval, and external agent (`HITL-*`)

- every reason code/answer schema; known value means no question;
- one grouped question, maximum rounds, timeout/expiry/cancel;
- valid/invalid/partial/extra/wrong-type answer;
- duplicate same answer, conflicting second answer, two tabs race;
- unauthorized user/role/external agent answer;
- answer after membership revocation or policy change;
- approval argument hash match/mismatch/override revalidation;
- approve/deny/expire/cancel; side effect executes once only after committed approval;
- every `approval_required` transition, including approve-with-overrides revalidation, deny to `APPROVAL_DENIED`, expiry, cancellation, restart, and duplicate decisions;
- malicious client fabricates approval/tool call/history;
- Pydantic deferred request serialized/resumed under pinned version;
- API restart/browser reconnect while waiting;
- external MCP receives `input_required`, resume token, polling/subscription, duplicate resume;
- parent-agent answer scoped to delegated command only;
- no direct external-agent route to user or broader permissions.

## 16. Revisions, dashboards, publication (`REV-*`)

- every revision class, direct control and chat equivalent command;
- style revision keeps data/result hash and no worker/model where deterministic;
- binding revision keeps source/result hash and no analysis run;
- transform/analytical revision creates correct child lineage and recomputation;
- stale revision, commutative presentation auto-rebase, noncommutative conflict;
- branch, compare, undo-as-new-revision, redo, pin, copy, delete/tombstone;
- cross-filter dependency DAG, cycle rejection, widget failure isolation;
- publish only final/exact-proven or verified; immutable published revision;
- access/expiry/unpublish; export draft watermark; export failure isolation;
- concurrent editors and multi-tab optimistic state convergence.

## 17. Model/provider behavior (`MOD-*`)

- approved catalog returned by server; unknown/provider string rejected;
- `auto/fast/balanced/deep` resolution and capability/data-policy compatibility;
- model switch cannot change tool/data authority;
- pin model per logical step; fallback recorded; incompatible fallback denied;
- timeouts, 429, 5xx, invalid auth, safety refusal, empty/truncated/invalid structured output;
- tool retry versus output retry versus transport retry budgets; no retry storm;
- token/context/request/cost ceilings;
- prompt/skill/model/catalog version attached to run;
- raw restricted rows never sent; provider request redaction test;
- deterministic TestModel/FunctionModel tests prove tool and path constraints.

## 18. Security/adversarial (`SEC-*`)

- prompt injection in filename/header/cell/metric description/retrieved skill/MCP output;
- data exfiltration requests, cross-tenant references, secret requests, system-prompt requests;
- SQL injection, AST bypass, comments/encoding/multi-statement, unsafe functions/files/extensions;
- SSRF, DNS rebinding, URL redirects, private/link-local/metadata endpoints;
- path traversal, symlink, archive traversal, object key manipulation;
- XSS in Markdown/SVG/tooltip/export, prototype pollution, CSV/Excel formula injection on export;
- CSRF, CORS/origin, session fixation, replay, websocket/SSE auth expiry;
- denial of wallet/service: huge prompts, recursive plans, tool loops, high-cardinality renders, export bombs;
- MCP confused deputy, tool-name collision, schema swap, malicious server, transport downgrade;
- telemetry/log injection and sensitive-data redaction;
- dependency compromise simulation and feature-disable kill switch.

## 19. Performance and capacity (`PERF-*`)

Workloads are defined in `tests/performance/workloads.yaml` with source hash and reproducible generators:

- tiny: 100 rows/10 columns;
- small: 10k/30;
- medium: 1m/50;
- large: policy maximum uploaded bytes/rows;
- wide: maximum columns;
- high-cardinality, long strings, spatial, and multi-widget dashboard variants.

Measure p50/p95/p99:

- command acceptance, first status, first artifact shell, first useful data, final artifact;
- ingest/profile, query, result validation, renderer, export;
- reconnect recovery, cancellation acknowledgement;
- CPU/memory/temp disk, event queue depth/lag, DB connections, object throughput;
- model tokens/cost/requests/tool calls per successful task.

Run cold/warm cache, one user, target concurrency, 2× expected burst, 8-hour soak, and dependency rate-limit conditions. Exact numeric SLO targets are frozen in `05_SECURITY_OPERATIONS_AND_DELIVERY.md` after Phase 0 measurement; correctness/security never trade for latency.

## 20. Chaos, durability, migration, recovery (`CHAOS-*`, `MIG-*`)

Inject termination/disconnect at every persisted state boundary:

- API restart before/after transaction/outbox commit;
- worker crash before/after object upload and result commit;
- event delivered before client ack; duplicate queue delivery;
- Postgres failover/read-only/deadlock/connection exhaustion;
- Redis flush/outage; no authoritative loss;
- object store timeout/partial/missing/corrupt/checksum mismatch;
- model/MCP/Mapbox/provider outage and circuit breaker;
- DBOS process restart/checkpoint replay/duplicate step side effect;
- deploy old/new API/worker concurrently during additive migration;
- rollback after forward migration;
- backup restore to isolated environment and hash/audit verification;
- region/zone failure according to selected deployment topology.

Invariants after every test: no duplicated side effect, no invalid terminal state, no cross-tenant data, no lost committed revision/event, hashes reconcile, resumable work resumes or fails explicitly, and cleanup is bounded.

## 21. CI/release gates

Every PR:

- format/lint/type/schema drift;
- unit/property/contract/component tests;
- critical integration/E2E/security subset;
- critical agent-eval subset with baseline comparison when prompts/models/skills/tools/contracts change;
- dependency/license/secret scan.

Release:

- all tests in this matrix pass on the exact images being promoted;
- 100% requirements traceability and critical mutation score;
- zero known severity-0/1 defects and zero open correctness/security/exactness defect;
- no quarantined/flaky critical test; noncritical flaky tests have owner/expiry and cannot hide failures;
- full eval gates, load/soak, chaos/recovery, migration/rollback, accessibility, visual, backup/restore pass;
- test artifacts and seeds stored with the release evidence packet.

Tests MUST NOT be updated merely to bless changed behavior. A normative spec/ADR and regression explanation precede expected-output changes.
