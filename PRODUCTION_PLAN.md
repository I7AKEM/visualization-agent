# Production Visualization Agent — source-of-truth plan

Status: round-three implementation specification complete; WP-00 governance baseline recorded; runtime not yet implemented
Research date: 2026-08-29
Purpose: preserve the important decisions, caveats, sources, and implementation order when conversation context is compacted.

Implementation is governed by the normative specification package in [`docs/production-spec/`](docs/production-spec/README.md):

- [`01_DECISIONS_AND_ARCHITECTURE.md`](docs/production-spec/01_DECISIONS_AND_ARCHITECTURE.md): frozen responsibilities, modes, topology, and trust boundaries;
- [`02_CONTRACTS_AND_STATE_MACHINES.md`](docs/production-spec/02_CONTRACTS_AND_STATE_MACHINES.md): exact API/domain/event models, clarification/approval, state transitions, retries, errors, idempotency, and revisions;
- [`03_TEST_AND_FAILURE_MATRIX.md`](docs/production-spec/03_TEST_AND_FAILURE_MATRIX.md): code, contract, property, fuzz, mutation, integration, E2E, security, accessibility, performance, and chaos coverage;
- [`04_AGENT_EVAL_SPEC.md`](docs/production-spec/04_AGENT_EVAL_SPEC.md): versioned agent datasets, cases, evaluators, model matrix, hard thresholds, and online learning loop;
- [`05_SECURITY_OPERATIONS_AND_DELIVERY.md`](docs/production-spec/05_SECURITY_OPERATIONS_AND_DELIVERY.md): security controls, telemetry, SLOs, alerts, incidents, CI/CD, rollback, and implementation work packages;
- [`06_TASK_DISPATCH_BRIEFS.md`](docs/production-spec/06_TASK_DISPATCH_BRIEFS.md): isolated task ownership, dependency evidence, deterministic handoff commits, and integration acceptance.

Those files take precedence over estimates or shorthand in this document. An unanswered implementation question requires a reviewed spec/ADR amendment; it must not become an undocumented code decision.

## 1. Product objective

Build a production-grade, Arabic/English **visualization-first workspace** where a user can:

- chat with an agent;
- upload CSV, TSV, Excel, JSON, or Parquet data and later connect governed databases;
- see analysis progress and visual artifacts render live, before the full answer finishes;
- receive verified KPIs, tables, charts, maps, dashboards, and narrative summaries;
- revise any generated artifact by chat or direct UI controls;
- branch, compare, undo, publish, and export revisions;
- choose an approved model or an `auto`, `fast`, `balanced`, or `deep` mode in the UI;
- inspect what metric, filters, data version, query, and assumptions produced every number;
- explicitly lock a request to **render the selected rows and fields exactly as supplied**, with no aggregation, calculated fields, sampling, sorting, filtering, imputation, or other value-changing operation;
- operate safely in a multi-user, multi-tenant production environment.

Product identity: **Visualization Agent / Visual Analytics Workspace**, not a generic autonomous data agent. Visualization is always available; data transformation and analysis are optional capabilities selected only when the request needs them. A chart-ready dataset can go straight to a validated renderer without invoking an analysis agent. When computation is requested, numerical truth must come from deterministic execution over a versioned dataset or governed semantic layer. The model interprets ambiguity, proposes plans, explains, and advises on presentation; the host application owns data, execution, validation, state, rendering, and review.

## 2. Non-negotiable decisions

1. **Pydantic AI is the backend agent SDK.** Use typed dependencies, tools, outputs, retries, model selection, UI event adapters, Pydantic Evals, and Logfire/OpenTelemetry. Pydantic AI supports model portability, structured output, MCP, Vercel AI and AG-UI streams, and durable execution. See the [Pydantic AI overview](https://pydantic.dev/docs/ai/overview/).
2. **Use the Vercel AI Data Stream Protocol for the first web product.** Pydantic AI has a native `VercelAIAdapter`, and its data chunks can carry typed custom payloads to the frontend. Use AI SDK UI `useChat` for transport/state and Ant Design X for the visible chat experience. See [Pydantic's Vercel AI integration](https://pydantic.dev/docs/ai/integrations/ui/vercel-ai/).
3. **Rendering must be live.** Create the visual shell as soon as the artifact type is known, then stream typed data/spec patches into the mounted renderer. Do not wait for the complete LLM answer, complete dashboard, or static PNG.
4. **Do not execute arbitrary model-generated React, JavaScript, Python, or HTML.** The model emits validated plans, specs, and patches from an allowlisted component catalog.
5. **Do not make raw model-generated SQL the default analysis contract.** Prefer a typed `AnalysisPlan` compiled by code. If SQL is produced for a governed database, parse and policy-check its AST, dry-run it, execute it read-only in an isolated worker, and verify its results.
6. **Mapbox GL JS is the default map renderer.** L7 is not China-only—it is a global WebGL geospatial engine—but some ready-made AntV MCP map tools and example basemaps are China-oriented. Use Mapbox for Saudi/global basemaps, boundaries, points, paths, choropleths, clusters, heatmaps, and live layers. Mapbox supports live `GeoJSONSource.setData()` updates and vector tiles for large data. See [real-time feature updates](https://docs.mapbox.com/mapbox-gl-js/example/live-update-feature/) and [Mapbox sources/layers](https://docs.mapbox.com/mapbox-gl-js/guides/add-your-data/style-layers/).
7. **The AntV chart MCP is not the product's analysis authority.** Use it as an optional external interoperability or server-side export adapter. Use GPT-Vis/G2/S2/etc. directly for the interactive product.
8. **MCP is for agent-to-tool interoperability.** It is useful for external data/services and for exposing trusted tools to other clients. It is not required between every internal service. Pydantic AI supports MCP clients and servers: [MCP overview](https://pydantic.dev/docs/ai/mcp/overview/).
9. **A2A is not on the critical path.** Browser UI communication should use Vercel AI or AG-UI. Add an A2A adapter later only if remote agents genuinely need discovery/delegation. Do not delay the product for A2A.
10. **Every artifact and every computation is immutable and versioned.** Revisions create a child version rather than silently mutating a published result.
11. **Uploaded data is untrusted.** It can contain prompt injection text, malformed values, formulas, huge rows, malicious paths, and sensitive data. Treat all cell contents as data, never as instructions.
12. **No data goes to AntV's public rendering service in production.** Interactive rendering stays in the browser; private server-side export uses a self-hosted renderer.
13. **Analysis is not the default entry point.** The request router selects the cheapest sufficient mode. Explicit UI actions take precedence over model inference, and a `render_only` lock is a hard policy constraint.
14. **Never silently change what is displayed.** Every artifact declares `data_mode: exact | transformed | aggregated | sampled`. Sampling or aggregation requires a visible user choice and can never be mislabeled as exact.
15. **The host is authoritative.** Models and external skills may propose intent, bindings, transforms, or designs, but only typed, validated host operations can read data, execute work, persist state, or reach a renderer.

### 2.1 Round-two validation against current open-source systems

The architecture is consistent with the strongest current open-source patterns, with one important correction: **do not force every visualization through an analysis agent**.

| Reference system | Pattern worth adopting | Boundary for this product |
|---|---|---|
| [Microsoft Data Formulator](https://github.com/microsoft/data-formulator) | Blends drag-and-drop, natural-language transformation, recommendations, full agent mode, branching, direct chart refinement, and reports. Its published control levels validate having both exact/direct and agentic paths. | It is a research/open-source reference, not proof that its default local deployment is sufficient for this product's tenant, security, or SLO requirements. |
| [Microsoft Flint agent workflows](https://github.com/microsoft/flint-chart/blob/main/docs/tutorials/agent-workflows.md) | The host owns execution, validation, state, UI controls, compilation, rendering, and review; the agent proposes semantic chart intent. Routine UI edits remain deterministic. | Evaluate Flint as a reusable common-chart semantic contract/compiler, but do not force Mapbox, S2, KPI cards, G6, or Infographic into a chart-only schema. |
| [AntV GPT-Vis](https://github.com/antvis/GPT-Vis) | AI-friendly syntax/JSON, fault-tolerant incremental chart rendering, and a ready-made common-chart renderer. | It is a renderer, not the data truth, security, revision, or analytical execution layer. |
| [AntV AVA](https://github.com/antvis/AVA) | Modular data, metadata, analysis, and optional visualization stages. | Current v4 direction is experimental; candidate insights must be verified elsewhere. |
| [Vizro](https://github.com/mckinsey/vizro) | Declarative dashboard components and controls; current AI integration moving toward MCP reinforces keeping AI as an adapter. | Do not add a second full UI framework unless a concrete dashboard feature justifies it. |
| [Microsoft LIDA](https://github.com/microsoft/lida) | Useful earlier reference for multi-stage visualization generation/evaluation and grammar-agnostic outputs. | Research/prototype reference; it does not replace the production host, policy, and eval layers. |

Conclusion: open-source visualization agents often generate charts or analysis successfully, but few provide the complete multi-tenant build/eval/observe/deploy system. This plan intentionally combines proven OSS components behind stable contracts and adds the missing operational controls. The architecture should be called **host-owned visual analytics with optional agents**, not “one large data agent.”

## 3. What to keep and what to change in the current POC

### Keep

- The central principle in `agent/fast_track.py`: a model chooses a plan from schema/sample context, while code computes the numbers.
- The tested private AntV rendering path, Arabic font handling, and tool filtering.
- Existing AntV experiments as compatibility and visual-regression fixtures.

### Replace or expand

- `Plan` currently supports only a small chart list, equality filters, and `sum|mean|count`. Replace it with a richer typed `AnalysisPlan` plus a separate `VisualizationSpec`.
- `fast_track.py` currently loads the entire CSV through `csv.DictReader`, profiles a small sample, performs naïve string/date handling, and stores a global file cache. Replace this with streamed upload, DuckDB/Arrow/Parquet execution, robust type inference, explicit tenant and dataset version keys, and a real cache.
- `agent/main.py` currently sends full CSV text to the model and tells it to calculate totals, growth, and shares. Retire this as a production path. The model must receive compact verified results or result references, not become the calculator.
- The current line-growth explanation compares the lexically first and last values. Production logic must use parsed time types, declared time grain, missing-period handling, and comparison semantics.
- The current top-N logic folds the remainder into `Other` without retaining lineage. Production results must preserve the complete result and record the exact display transform.

### Corrections to `REPORT.md`

- Do not keep Vanna 2.0 as the long-term core. The [Vanna repository was archived on 2026-03-29](https://github.com/vanna-ai/vanna). If temporarily retained, isolate it behind a `TextToQueryProvider`, pin/fork it, add security controls, and maintain a migration path.
- Do not describe AVA output as verified truth. The current [AntV AVA repository](https://github.com/antvis/AVA) labels the active direction experimental. Use AVA only to propose candidate trends/outliers/chart choices, then verify each candidate with deterministic code and statistical rules.
- L7 is not limited to China. The engine can visualize global data, but the existing MCP map tools and examples may not fit Saudi/global product requirements. Mapbox is the production default.
- The MCP-to-static-PNG path is useful for exports and external clients, but it is not the primary interactive UI path.

## 4. Target architecture

```text
Browser / Next.js
  Ant Design X chat + Ant Design/ProComponents shell
  AI SDK useChat
  Live Artifact Store + Renderer Registry
  GPT-Vis/G2 | S2 | Mapbox GL JS | G6/Graphin | Infographic | React KPI cards
          │
          │ SSE: Vercel AI events + typed data-* chunks
          ▼
FastAPI / Pydantic AI
  Auth + tenant context + model policy
  Deterministic intent/mode router
  Direct render/binding service
  Conversation orchestrator
  Typed analysis planner
  Revision classifier
  Visualization advisor/spec builder
  Narrative generator
          │
          ├── Upload/profile service
          │     object storage → DuckDB/Arrow → canonical Parquet
          │
          ├── Analysis execution workers
          │     Ibis/typed compiler → DuckDB for uploads
          │     governed semantic/query provider for warehouses
          │
          ├── Validation and insight workers
          │     reconciliation, quality checks, statistical methods
          │
          └── Postgres + Redis + object storage
                metadata/revisions/audit + cache/events + datasets/results/exports
```

Recommended deployable units:

- `web`: Next.js/React frontend;
- `api`: FastAPI/Pydantic AI streaming API;
- `worker-analysis`: isolated query and profiling worker;
- `worker-export`: private PNG/PDF/infographic export worker;
- Postgres: identities, conversations, semantic metadata, plans, runs, artifacts, revisions, audit;
- Redis: short-lived cache, rate limiting, distributed event coordination;
- S3-compatible object storage: uploads, canonical Parquet, result snapshots, exports;
- DBOS-backed background durability/queues for profiling, large queries, report generation, export, cleanup, and scheduled refresh; Postgres remains authoritative for interactive command/state/outbox persistence.

### 4.1 Operating modes and request router

Use one product with a discriminated `RequestIntent`, not separate chatbots. The user may choose a mode explicitly; otherwise a deterministic router uses UI state and request features, with a small model classifier only for remaining ambiguity.

| Mode | When to use | Data operations allowed | Agent requirement |
|---|---|---|---|
| `render_only` | “Plot these columns,” user selected a chart/fields, or data is already chart-ready | parsing and type validation only; preserve values and row order | none when UI intent is complete; optional chart-advice call only |
| `visual_transform` | user explicitly asks to filter, sort, bin, reshape, calculate a field, normalize, or prepare chart-ready data | only the declared, previewed, non-destructive transform plan | planner may propose; host executes and validates |
| `analyze` | KPI, aggregation, comparison, joins, statistics, insight discovery, forecasting, or business questions | typed analysis plan and deterministic/statistical execution | agent plans/explains; host computes |
| `compose` | combine existing verified artifacts into a dashboard/report/infographic | layout, style, filters, and declared cross-widget bindings; no implicit recomputation | optional layout/narrative assistance |
| `revise` | change an existing artifact | presentation, binding, transform, or analysis path based on a typed revision class | none for deterministic UI edits; agent only for ambiguous natural language |

Core union:

```text
RequestIntent =
  RenderIntent | TransformIntent | AnalyzeIntent | ComposeIntent | ReviseIntent
```

The UI must expose:

- an always-visible `Use data exactly as uploaded` lock;
- current mode and a plain-language list of permitted operations;
- a preview/approval step before crossing from `render_only` into transform or analysis;
- chart/field bindings, style, sort, aggregation, and sampling controls that clearly distinguish visual changes from data changes;
- a data view showing the exact rows behind the current artifact and its lineage.

`render_only` invariants:

- `transformations=[]`, `analysis_plan_id=null`, and `data_mode="exact"`;
- the ordered value fingerprint of the renderer input equals the selected source view fingerprint;
- no DuckDB/Ibis analysis worker, generated SQL, aggregate, calculated field, implicit sort, imputation, top-N, `Other`, downsampling, or AI-written code;
- formatting may change labels but never stored values; parsing metadata retains raw tokens for audit;
- a direct chart choice and field binding can bypass the LLM completely;
- if a requested chart mathematically requires a derived distribution or summary—histogram, box plot, aggregate choropleth, percentage share—the UI explains why and asks permission to switch modes;
- if exact rendering exceeds renderer limits, show the limit and offer filter, aggregation, sampling, or a table/virtualized alternative. Never silently sample.

This matches Data Formulator's spectrum from direct drag-and-drop to agent mode and Flint's host-owned workflow. It also lowers latency and model cost for the large class of requests that are purely visual.

## 5. Data and analysis lifecycle

### 5.1 Upload and canonicalization

1. Browser uploads directly to object storage with a short-lived signed URL.
2. Enforce file count/size/type limits, MIME and extension checks, decompression limits, virus scanning where required, and tenant-scoped paths.
3. Fingerprint the bytes and create an immutable `DatasetVersion`.
4. Detect encoding, delimiters, headers, dates, decimals, Arabic/Western digits, null tokens, duplicate headers, and malformed rows.
5. Convert accepted tabular data to typed Parquet. Keep the original file for audit but query the canonical version.
6. Produce a profile: row count, column types, nulls, distinct count, min/max, quantiles, sample values, possible IDs, units, currencies, time zones, and potential geographic fields.
7. Show the profile live and ask the user only about consequential ambiguity—for example, whether `03/04/26` means March 4 or April 3, whether an amount is SAR or halalas, or whether duplicate IDs are expected.

DuckDB can infer CSV structure and query Parquet efficiently, but untrusted SQL/file paths require isolation. DuckDB explicitly says to treat SQL like code and recommends sandboxing, external-access restrictions, extension restrictions, timeouts, and resource limits: [DuckDB security guidance](https://duckdb.org/docs/current/operations_manual/securing_duckdb/overview).

Canonicalization is storage normalization, not permission to change the user's meaning. Preserve the original bytes, raw cell token, row ID/order, inferred typed value, parse status, and any warning. A `render_only` artifact can use the typed view for rendering only when round-trip/fingerprint checks prove equivalence; otherwise it must fall back to raw display or request clarification.

### 5.2 Two semantic lanes

#### Lane A: ad-hoc uploads

- Build an ephemeral `DatasetSemanticProfile` from the uploaded version.
- Give fields stable IDs, types, display names, roles (`measure`, `dimension`, `time`, `geo`, `identifier`), units, default aggregation, and confidence.
- Never silently invent business metrics. Ask the user to confirm ambiguous denominators, units, cohort rules, or joins.
- Let the user save a confirmed profile as a reusable governed dataset later.

#### Lane B: governed databases and warehouses

- Use an existing semantic layer whenever available. Do not let each model redefine `revenue`, `active user`, `conversion`, or joins.
- Preferred reusable choices:
  - dbt/MetricFlow when the organization already uses dbt. It centralizes metrics and handles semantic joins; it supports simple, ratio, cumulative, derived, and conversion metrics. See [dbt Semantic Layer](https://docs.getdbt.com/docs/use-dbt-semantic-layer/dbt-sl) and [MetricFlow](https://docs.getdbt.com/docs/build/about-metricflow).
  - WrenAI when an open, agent-oriented context/semantic layer is needed across sources. Its OSS core includes MDL, governed text-to-SQL, dry planning, row limits, structured errors, and connectors. Important: row/column security, user/group access control, and its GenBI UI are commercial, so application-level authorization is still required unless that edition is procured. See [WrenAI's OSS/commercial boundary](https://github.com/Canner/WrenAI#open-core-oss-vs-cloud--self-hosted).
- Vanna may be supported only through a temporary compatibility adapter because its repository is archived.

### 5.3 Calendar, locale, and temporal semantics

Calendar and time zone are separate concerns and must never be inferred from the Arabic language alone.

- Use ISO-8601 Gregorian dates/timestamps as the canonical computation key. Store instants in UTC plus the source time zone; preserve date-only values as date-only values rather than converting them to UTC midnight.
- Preserve `raw_value`, `source_calendar`, `calendar_confidence`, `source_timezone`, `locale`, and the conversion library/data version. Supported calendar values begin with `gregory`, `islamic-umalqura`, `islamic-civil`, and `unknown`.
- For Saudi Hijri data, default to **Umm al-Qura only when declared by the dataset/user or confidently identified and confirmed**. “Hijri” is ambiguous because tabular/civil and Umm al-Qura calendars can differ.
- Use the stable Python [`hijridate`](https://pypi.org/project/hijridate/) package for verified backend Umm al-Qura conversion and pin its version. Its documented official-source range is 1343–1500 AH / 1924-08-01–2077-11-16; reject or explicitly route dates outside that range rather than silently using another algorithm.
- Use browser `Intl.DateTimeFormat` with `calendar: "islamic-umalqura"` or locale `ar-SA-u-ca-islamic-umalqura` for display, but do not use browser formatting as the analytical conversion authority. Engines may fall back outside their supported range. See [supported Intl calendar identifiers](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/supportedValuesOf).
- Store filters as canonical half-open time ranges plus their user-facing Hijri/Gregorian expression and conversion version. Test 29/30-day months, year boundaries, Ramadan/Hajj periods, leap behavior, incomplete periods, and conversions against an authoritative Saudi calendar fixture.
- Provide Arabic and English month labels, Arabic-Indic/Western digit preferences, dual-calendar tooltips/axes, week-start policy, fiscal calendar metadata, and `Asia/Riyadh` defaults where the workspace declares Saudi context.
- Future or religious observance dates may change by official announcement; label computed conversions as calendar dates, not religious rulings. The [Saudi official gazette](https://www.uqn.gov.sa/) and [Umm al-Qura calendar](https://www.ummulqura.org.sa/) are reference fixtures, not runtime scraping dependencies.

### 5.4 Typed analysis contract

The model returns an `AnalysisPlan`; it does not return the final numbers. At minimum the plan contains:

- dataset and semantic-model version IDs;
- user question and clarified analytical intent;
- selected metric IDs and exact definitions;
- dimensions/groupings;
- filters with typed operators and values;
- time field, grain, range, comparison period, time zone, and missing-period policy;
- aggregation and distinct-count semantics;
- numerator/denominator for ratios;
- sort, limit, top-N, and `Other` policy;
- required joins through approved relationships;
- optional statistical method and assumptions;
- expected output grain and schema;
- privacy classification and execution budget.

Use a discriminated Pydantic union for intent-specific plans such as `KPIPlan`, `TrendPlan`, `ComparisonPlan`, `DistributionPlan`, `RelationshipPlan`, `GeoPlan`, and `TablePlan`.

### 5.5 Compilation, policy, and execution

- Prefer code to compile the typed plan using Ibis expressions. [Ibis](https://ibis-project.org/why) provides one dataframe-style expression API that compiles to backend-native queries and uses DuckDB by default locally.
- For SQL supplied by a semantic provider, use SQLGlot for AST inspection, allowed statement/table/function checks, dialect normalization, lineage, and revision diffs. SQLGlot is intentionally lenient and explicitly is **not** a validator, so parsing never replaces dry-run and sandboxed execution. See [SQLGlot documentation](https://sqlglot.com/sqlglot.html).
- Enforce read-only credentials, tenant/row policy before query construction, approved tables and joins, statement/time/row/byte limits, and cancellation.
- DuckDB workers must run in a minimal container/process with network disabled, restricted paths, preinstalled allowlisted extensions only, external access disabled after loading the tenant file, locked configuration, and memory/thread/temp limits.
- Store the compiled query, normalized AST/hash, parameters, engine version, start/end time, rows scanned/returned, and warnings in `AnalysisRun`.

### 5.6 Result validation

Before a result can be marked final:

- validate the returned schema and grain against the plan;
- reject duplicate keys where uniqueness was expected;
- reconcile totals, subtotals, top-N and `Other` values;
- verify ratio denominators and divide-by-zero handling;
- validate units/currency/time zone and formatting metadata;
- detect missing periods and partial current periods;
- check null and sample-size thresholds;
- rerun critical aggregates through an independent/simple reference path in golden tests;
- attach `provisional`, `warning`, or `final` status to every result.

Use [Great Expectations](https://docs.greatexpectations.io/docs/core/define_expectations/) for saved/governed datasets with stable data contracts. For a one-off arbitrary upload, start with lightweight profiling and warnings; allow confirmed rules to be promoted into an Expectation Suite.

### 5.7 Insight generation

- Generate candidates with deterministic methods first: comparisons, contribution/share, ranking, deltas, rolling changes, distribution summaries, missingness, and outlier/seasonality methods appropriate to the data.
- AVA may contribute candidates, never final claims.
- Every `InsightCandidate` stores method, inputs, sample size, baseline, effect size, uncertainty, assumptions, and supporting result-cell IDs.
- Do not imply causation from observational data. Do not promote a p-value as importance. The ASA notes that statistical significance does not measure effect size or practical importance and recommends transparent reporting of uncertainty: [ASA statement](https://www.amstat.org/asa/files/pdfs/p-valuestatement.pdf).
- The language model converts verified candidates into concise Arabic/English narrative, but every numerical claim must resolve to a result cell or computed insight object.

## 6. Visualization and component registry

The backend returns one stable product-level **artifact envelope** with typed, renderer-specific variants; it does not invent a universal lowest-common-denominator chart language or return raw React/JavaScript. Reuse upstream declarative contracts where they are strong—for example GPT-Vis JSON/vis syntax, an evaluated Flint `ChartAssemblyInput`, G2 Spec, Mapbox style/source fragments, and S2 configuration—then wrap them with product-owned lineage, mode, policy, revision, and validation metadata.

| Artifact | Default renderer | Purpose |
|---|---|---|
| Common chart | GPT-Vis first; G2/Ant Design Charts for advanced grammar; Flint evaluation is post-release | line, area, bar, column, pie/donut, scatter, histogram, box plot, heatmap, funnel, sankey, etc. |
| KPI/scorecard | allowlisted custom React components with design tokens and motion presets | KPI, target/variance, trend sparkline, status, progress, alerts |
| Analytical table | Ant Design Table / ProTable | normal result table, sorting, pagination, drill actions |
| Pivot/crosstab | AntV S2 | multidimensional cross-analysis and drill-down |
| Map | `react-map-gl` + Mapbox GL JS; optional deck.gl overlays | Saudi/global choropleths, symbols, clusters, heatmaps, routes, flows, time animation, high-volume WebGL layers, 3D where justified |
| Network/graph | G6 or Graphin | relationship and knowledge-graph analysis |
| Diagram editor | X6 only when editing a process/diagram is truly needed | not a normal business chart |
| Narrative visual | AntV Infographic | one-page explainers and report/export storytelling |
| Dashboard | ProComponents layout + registry widgets | grid, filters, tabs, cross-filtering, responsive composition |

Reuse [GPT-Vis](https://github.com/antvis/GPT-Vis) for AI-friendly, fault-tolerant streaming of common charts and [AntV chart-visualization-skills](https://github.com/antvis/chart-visualization-skills) as a retrieved chart-selection/best-practice knowledge source. Do not copy its content into prompts permanently; pin a reviewed version and retrieve only relevant material. GPT-Vis reports support for streaming and JSON specs, while the AntV skill repository covers chart selection plus G2/G6/S2/Infographic patterns. Release 1 uses the AntV adapters. Evaluate [Microsoft Flint](https://github.com/microsoft/flint-chart) only after the stable artifact envelope ships; adoption then requires chart coverage, RTL/accessibility, bundle cost, deterministic compilation, and renderer-fidelity evidence.

Map notes:

- Small/medium live geographic results: stream GeoJSON feature batches and call Mapbox `setData()` at a throttled cadence.
- Large geographic results: generate/vector-tile data by viewport/zoom; do not ship every feature as one GeoJSON object.
- Use licensed Mapbox Boundaries or an authoritative, licensed Saudi boundary dataset with stable region IDs. Never join regions by fragile display spelling alone.
- Keep data layers separate from the basemap so a future MapLibre/self-hosted deployment is possible if procurement or sovereignty requirements change.

### 6.1 Geospatial-temporal contract

Geospatial-temporal visualization is a first-class artifact type, not a generic chart with latitude and longitude columns.

Data contract:

- canonical geometry is valid GeoJSON/OGC geometry in WGS84 (`EPSG:4326`) with explicit longitude/latitude order; retain original CRS and transformation provenance;
- validate geometry type, coordinate bounds, polygon validity, antimeridian behavior, stable feature/region IDs, and licensed boundary version;
- distinguish `event_time`, `valid_from`/`valid_to`, and `recorded_at`; routes may carry one timestamp per vertex;
- declare geographic grain (`point`, `route`, `admin_region`, `grid`, `hex`, `tile`) and temporal grain/time zone/calendar;
- bind Saudi regions by authoritative stable IDs and bilingual names, never by fuzzy display text alone;
- enforce location privacy, minimum aggregation thresholds, and coordinate rounding/redaction where points could identify people or sensitive facilities.

Rendering/execution:

- use controlled [`react-map-gl`](https://visgl.github.io/react-map-gl/docs) state so map camera, filters, timeline, chat, and dashboard controls remain synchronized;
- use Mapbox GeoJSON sources with throttled `setData()` for small/medium live batches and vector tiles/viewport queries for large sources; Mapbox's [real-time update example](https://docs.mapbox.com/mapbox-gl-js/example/live-update-feature/) confirms that `setData()` starts a render cycle;
- add [deck.gl](https://deck.gl/docs/api-reference/geo-layers/trips-layer) only for needs Mapbox layers do not cover well, such as large WebGL overlays, animated trips, or indexed geo layers. Lazy-load it and keep it behind the map adapter;
- use the [DuckDB spatial extension](https://duckdb.org/docs/stable/core_extensions/spatial/overview) in the isolated analysis worker for approved spatial joins/intersections/distance operations. Spatial computation is never part of `render_only`;
- stream a map shell, bounds and layer definition first, then feature/tile batches. A timeline can update the visible filter/playhead without waiting for the final dataset;
- normalize animation timestamps to avoid float precision loss in deck.gl `TripsLayer`; test DST/time-zone, out-of-order events, missing timestamps, cross-midnight routes, and Hijri-labeled time filters;
- secure Mapbox client tokens with least privilege and URL restrictions; secret-scope operations stay server-side. See [Mapbox security guidance](https://docs.mapbox.com/help/dive-deeper/how-to-use-mapbox-securely/).

## 7. True live rendering protocol

### 7.1 Required event sequence

Use typed Vercel AI `data-*` chunks for product artifacts. Suggested event types:

1. `data-run-status`: stage, progress, human-readable status;
2. `data-intent-resolved`: request mode, source view, `data_mode`, allowed operations, and whether an agent/worker is involved;
3. `data-dataset-profile`: incremental schema/profile updates;
4. `data-artifact-create`: artifact ID, kind, title placeholder, renderer, `preview` state;
5. `data-binding`: source fields, visual channels, exactness/fingerprint metadata;
6. `data-analysis-plan`: compact approved plan summary, emitted only for transform/analysis work;
7. `data-result-schema`: fields, types, units, grain, calendar, time zone, and geographic metadata;
8. `data-result-batch`: append/upsert rows, features, or tile references with sequence/cursor;
9. `data-visualization-patch`: validated spec/style/layout patch;
10. `data-insight`: verified insight with provenance;
11. `data-artifact-finalize`: final spec/result/source hashes and warnings;
12. `data-run-error`: scoped failure and recoverable action.

### 7.2 Frontend behavior

- Mount a skeleton card/dashboard grid immediately on `artifact-create`.
- Instantiate the actual renderer when its minimal valid spec arrives.
- In `render_only`, send the shell/spec immediately after bindings validate and begin streaming source batches directly; do not wait for profiling, narrative, or any model call to finish.
- Apply patches by stable artifact ID; batch/throttle repainting to avoid jitter.
- Keep a visible `Preview—computing` badge until reconciliation and finalization.
- Never present partial top-N order, percentage share, anomaly, or total as final. It may animate provisionally, but the UI must label it as incomplete and reconcile at the end.
- Stream dashboard widgets independently. One failed widget must not block or erase completed widgets.
- Persist the event log or the reduced final artifact state so reconnect/resume does not require a full rerun.
- Include monotonic per-artifact sequence numbers, idempotency keys, resumable cursors, and periodic state snapshots so reconnects cannot duplicate or reorder data.
- Treat renderer-ready progress and analytical finality separately. `render_only` may finalize as soon as all exact source batches and fingerprints reconcile; analytical artifacts remain provisional until result validation completes.
- Cancellation must stop the model and query worker and retain the useful partial artifact as an explicitly incomplete draft.

Pydantic's adapter supports custom `DataChunk` payloads alongside text/tool events, which is the key transport primitive for this design: [Data chunks](https://pydantic.dev/docs/ai/integrations/ui/vercel-ai/#data-chunks).

## 8. Conversational and direct chart revision

Users must be able to say or click:

- “Make it a horizontal bar chart.”
- “Use our ministry palette and animate the entrance.”
- “Show Q2 only.”
- “Change revenue to margin.”
- “Group by region instead of channel.”
- “Add a target line.”
- “Turn these three charts into a dashboard.”
- “Use a Saudi map and show transaction volume by region.”
- “Go back to version 2 and try a heatmap.”

### 8.1 Five revision kinds grouped into three execution strategies

#### Presentation-only revision — reuse the verified result

Examples: chart type when compatible with the current result shape, title, palette, labels, legend, number formatting, animation, size, grid position, annotation visibility, map camera, and theme.

The system creates a new `VisualizationRevision` but does not rerun the analysis. The result hash must remain unchanged.

#### Binding/composition revision — reuse the same exact source/result

Examples: bind a different existing field to x/y/color/size, facet the same rows, switch between compatible exact charts, move widgets, link an existing dashboard filter, or choose a different map property. No calculated field, filter, sort, grouping, aggregation, sampling, or join is introduced.

The system creates a new `VisualizationRevision` (or `DashboardRevision`) and revalidates field/channel compatibility, but does not create an `AnalysisRun`. In `render_only`, the source-view fingerprint remains unchanged. If the requested binding requires derivation—such as histogram bins or summed choropleth regions—the revision is reclassified and the user sees the proposed mode change.

#### Analytical revision — clone plan, validate, and re-execute

Examples: metric, aggregation, filter, time range/grain, comparison period, grouping, top-N, denominator, cohort, join, geographic level, or statistical method.

The system creates a child `AnalysisPlan`, new `AnalysisRun`, new `ResultSet`, and new `VisualizationRevision`. The UI keeps the old artifact visible until the new preview begins streaming.

### 8.2 Revision data model

```text
DatasetVersion
  └─ SourceView
      ├─ direct exact binding ──────────────────────┐
      └─ SemanticModelVersion                      │
          └─ AnalysisPlan (parent_plan_id optional)│
              └─ AnalysisRun                       │
                  └─ ResultSet ────────────────────┤
                                                  ▼
                    VisualizationRevision (parent_revision_id optional)
                      └─ DashboardRevision
```

Every patch includes `artifact_id`, `base_revision`, patch type, typed payload, actor, run/model ID, and client request ID. Use optimistic concurrency: reject or rebase a patch when `base_revision` is stale.

Required UX:

- chat and direct controls both emit the same typed patch commands;
- undo/redo and branch from any prior revision;
- side-by-side compare with analysis, result, and visual diffs;
- pin a preferred version and publish a read-only version;
- show “what changed” in plain language;
- for SQL-backed analysis, use AST-aware diffs rather than raw text diffs;
- cross-filter dashboard widgets through declared dependencies, not hidden prompt context.
- preserve the user's `render_only` lock across chat revisions until the user explicitly unlocks it.

Microsoft Research's Data Formulator is the reference interaction pattern: its Data Threads support branching, editable charts, direct refinement, and preserving analysis context instead of relying on one long chat. See the [Data Formulator repository](https://github.com/microsoft/data-formulator).

## 9. Model switching and runtime policy

- The UI displays approved product modes and models returned by the server, never an arbitrary provider string.
- Product modes:
  - `auto`: server selects based on complexity, risk, latency budget, and prior failure;
  - `fast`: schema questions, simple chart/style revisions, common summaries;
  - `balanced`: default multi-step analysis;
  - `deep`: ambiguous joins, complex comparisons, dashboard planning, or repair after validation failure.
- Use Pydantic AI `SelectModel` with authenticated run dependencies. It can choose a model from dependencies/history/usage at each logical model step: [Select Model](https://pydantic.dev/docs/ai/capabilities/select-model/).
- Pin a chosen model for each logical step/run so streaming does not switch providers mid-response.
- Store requested mode, resolved provider/model, model settings, prompt/capability versions, latency, tokens, and cost.
- Capabilities, data policy, and tools are server-owned. Switching models never grants additional data access.
- Add provider fallback only for compatible output/tool capabilities and record it visibly in the trace.

## 10. Security and governance

- Authenticate every request and derive tenant/workspace/user permissions on the server.
- Enforce dataset access before retrieval/planning, again before execution, and again before returning cached results.
- Use tenant-scoped object keys, encryption, retention, deletion, and audit policies.
- Redact or classify PII during profiling; avoid sending raw sensitive rows to model providers. Allow a private/local model route for restricted data.
- Server-held conversation history is authoritative. Frontend messages, metadata, tool results, and context are untrusted.
- Treat cell strings, column descriptions, uploaded filenames, and external documents as indirect prompt-injection content.
- Allowlist tools, tables, functions, visual components, map sources, file types, and outbound domains.
- Require human approval for high-cost exports/queries or sensitive external actions—not for normal read-only analysis.
- Produce an audit record for data access, semantic definitions used, query, result hash, artifact version, publication, export, and deletion.
- Never record raw upload content or full prompts in telemetry by default. Use hashes, IDs, redacted samples, and opt-in secure debugging.

## 11. Evaluation strategy and release gates

Use Pydantic Evals as the experiment harness. It supports code-first datasets, deterministic/custom/LLM evaluators, and span-based evaluation of internal tool behavior: [Pydantic Evals](https://pydantic.dev/docs/ai/evals/evals/).

### 11.1 Evaluation datasets

Build version-controlled Arabic and English suites from:

- current CSV fixtures and questions;
- real anonymized user questions and corrections;
- messy CSV/Excel cases: encoding, Arabic digits, missing rows, duplicate headers, mixed types;
- ambiguous metric/unit/time-zone questions;
- security cases: prompt injection in cells, forbidden paths/tables/functions, cross-tenant cache attempts;
- chart selection and accessibility cases;
- exact `render_only` cases proving no calculation, implicit transform, reorder, aggregation, sampling, or agent execution;
- conversational revision sequences, branching, undo, and stale revision conflicts;
- dashboard and map cases, including streamed layers, viewport/time filtering, CRS mistakes, invalid geometries, antimeridian crossing, and location-privacy thresholds;
- Gregorian, Umm al-Qura, Islamic-civil, ambiguous-Hijri, dual-calendar, Arabic-digit, date-only, time-zone, and out-of-supported-range cases;
- provider/model matrix cases;
- carefully selected BIRD/Spider-style cases for generalization, while treating domain-specific golden cases as the primary release signal.

Spider 2.0 demonstrates that real enterprise text-to-SQL requires large metadata contexts, multiple queries/dialects, and project documentation; benchmark models remain far weaker than older text-to-SQL tests. BIRD emphasizes dirty values, external business knowledge, and query efficiency. See [Spider 2.0](https://spider2-sql.github.io/) and [BIRD](https://bird-bench.github.io/).

### 11.2 Evaluator layers

1. **Contract:** valid Pydantic types, known intent/artifact/patch type, no arbitrary code, and legal mode transitions.
2. **Grounding:** correct dataset/model/metric/dimension/filter/time grain.
3. **Execution:** read-only policy, dry-run success, resource budget, correct result schema.
4. **Numerical truth:** exact golden cells/totals/ratios and reconciliation invariants.
5. **Insight quality:** supported effect, sample size/uncertainty, no causal overclaim.
6. **Visualization:** valid fields, appropriate encodings, chart allowlist, RTL, accessibility, exact-source invariants, calendar/geo semantics, renderer success, snapshot/visual regression.
7. **Revision:** correct classification, no recomputation for presentation/binding-only edits, required recomputation for analytical edits, unchanged hashes where expected, branch/undo integrity.
8. **Narrative:** every number traces to a result cell; no unsupported claim; correct Arabic/English formatting.
9. **Agent path:** expected tools and order, no raw full-data prompt, no forbidden tool, retry/repair bounded.
10. **System:** time to first status, first visible artifact, final artifact, cancellation, reconnect, tokens, cost, query bytes/rows, and peak memory.

### 11.3 Initial hard gates

- 100% tenant isolation, read-only policy, and forbidden-operation tests;
- 100% exact numerical match on deterministic golden cases;
- 100% `render_only` cases preserve ordered source values, execute no transform/analysis worker, and declare `data_mode="exact"`;
- 100% style-only revisions preserve `ResultSet` hash;
- 100% binding-only revisions preserve the source/result hash and create no analysis run;
- 100% analytical revisions create a new run/result;
- 0 unsupported numeric claims in the high-risk golden suite;
- 0 arbitrary code execution paths in normal product flows;
- no invalid visualization spec reaches a renderer;
- 100% supported-range Hijri conversion fixtures match the pinned authoritative reference set, with explicit failure outside the supported range;
- renderer and API error rates remain below the agreed SLO;
- no material quality regression for any approved UI model before release;
- latency/cost targets defined per dataset size and mode, with time-to-first-visible-artifact measured separately from time-to-final.

Do not use an LLM judge for arithmetic or security assertions. Prefer deterministic evaluators; reserve calibrated LLM judges and human review for subjective clarity/usefulness.

## 12. Observability and operations

Instrument the complete trace with Logfire/OpenTelemetry:

```text
request
  upload/profile
  semantic retrieval
  agent planning/model call
  plan validation
  query compilation/policy/dry-run
  execution
  result validation
  insight generation
  visualization selection
  stream first artifact/batches/finalize
  narrative
```

Logfire provides Pydantic AI instrumentation plus model/tool messages, tokens, cost, and OpenTelemetry-wide application traces: [Logfire AI observability](https://logfire.pydantic.dev/docs/ai-observability/).

Track at least:

- time to first status, artifact shell, first useful data, and final answer;
- upload/profile/query/render latency and failures;
- plan validation/retry/repair rates;
- bytes/rows scanned and returned;
- cache hit/miss/staleness and tenant-safe cache keys;
- model/provider latency, tokens, cost, fallback, cancellation;
- chart/revision types, requery rate, undo/correction rate;
- provisional-to-final changes;
- user feedback and published/exported artifacts;
- sampled online evaluation scores and safety violations.

Alert on security policy failures, cross-tenant access attempts, abnormal query resource use, repeated validation/renderer errors, cost spikes, severe latency regressions, and online faithfulness failures.

## 13. Deployment and reliability

- Build reproducible containers and pin Python/Node/package lockfiles.
- Use CI gates for unit, property, integration, eval, security, accessibility, visual regression, and load tests.
- Generate SBOMs and scan dependencies/images/secrets/licenses.
- Deploy preview environments for UI/renderer changes; run the golden eval suite before promotion.
- Use migrations for Postgres and artifact/spec schema versions.
- Canary model/prompt/library updates by workspace; retain instant rollback to prior versions.
- Run expensive/long analysis and exports through durable jobs with idempotency keys and resumable event delivery.
- Back up metadata and object storage, test restoration, and document RPO/RTO.
- Define SLOs for availability, streaming start, first artifact, final analysis, render success, and result correctness incidents.
- Separate interactive rendering from export rendering. A failure to create PNG/PDF must not destroy a valid live visualization.

## 14. Delivery roadmap

Assumption: a small product team of roughly 3–4 engineers plus product/design/data-domain support. Estimates are planning ranges, not commitments.

### Phase 0 — contracts and risk baseline (1 week)

- approve architecture decisions and the Pydantic data contracts;
- approve product identity, `RequestIntent` modes, `render_only` policy lock, and mode-transition UX;
- inventory current POC features/tests and preserve useful fixtures;
- define dataset classifications, tenant/auth model, target SLOs, and first golden eval set;
- replace outdated recommendations in `REPORT.md`.

Exit: reviewed schemas for Dataset, SourceView, RequestIntent, AnalysisPlan, ResultSet, ArtifactEnvelope/renderer variants, DashboardSpec, patches, revisions, and stream events.

### Phase 1 — production upload, exact rendering, and deterministic analysis foundation (2 weeks)

- object storage upload flow, dataset versions, DuckDB/Parquet profile worker;
- robust type/unit/time/geo profiling and ambiguity UI;
- `render_only` binding service, ordered fingerprints, exact-row streaming API, hard policy tests, and no-model fast path;
- typed plan compiler, sandbox, limits, cancellation, result validation;
- Postgres metadata/audit and tenant-safe caching.

Exit: chart-ready uploads render without an agent or computation and pass exactness gates; analytical requests answer golden KPI/trend/comparison/distribution questions with verified results and no model arithmetic.

### Phase 2 — live chat and renderer registry (2 weeks)

- Next.js + Ant Design X + AI SDK `useChat`;
- Pydantic Vercel AI adapter and custom live artifact chunks;
- GPT-Vis/G2 common charts, KPI cards, table, S2 pivot;
- Mapbox/react-map-gl base renderer, Saudi/global geographic identifiers, calendar-aware temporal controls, and an optional deck.gl spike;
- independent widget streaming and cancellation/reconnect.

Exit: visible renderers mount early and update progressively; no normal artifact waits for the complete assistant message.

### Phase 3 — revisions, dashboards, and insight verification (2 weeks)

- immutable artifact/revision graph;
- presentation vs binding/composition vs analytical revision classifier;
- direct controls and chat patches through one command model;
- undo/redo, branch, compare, pin, publish;
- deterministic insight methods plus candidate verification;
- dashboard grid, global filters, cross-widget dependencies.

Exit: the full revision test suite passes, including hash invariants and streaming re-analysis.

### Phase 4 — governed data and model matrix (2 weeks)

- adapter interface for dbt/MetricFlow and/or WrenAI;
- read-only warehouse connectors, approved semantic retrieval, SQL policy/dry-run;
- approved model catalog, UI mode/model selection, auto routing, fallback policy;
- MCP adapters for selected external tools and optional external visualization service access.

Exit: at least one governed source passes domain golden queries and access-policy tests across approved models.

### Phase 5 — evals, observability, exports, and production hardening (2 weeks)

- complete Pydantic Evals gates and model/prompt comparison reports;
- Logfire/OpenTelemetry dashboards, redaction, alerts, and online sampling;
- self-hosted PNG/PDF/Infographic export and Arabic/RTL visual regression;
- load/soak/failure/recovery testing, CI/CD, canary and rollback.

Exit: security review, operational runbooks, SLO dashboards, recovery test, and release checklist complete.

### Phase 6 — controlled beta and learning loop (2+ weeks)

- onboard a small set of users and domain experts;
- collect corrections, failed questions, desired revisions, and time-to-insight;
- convert reviewed failures into permanent eval cases;
- only then expand connectors, visual types, and autonomous behaviors.

## 15. Skill and MCP packaging

The existing `pydantic-stack-lifecycle` skill is valuable for the Pydantic build/eval/monitor/deploy lifecycle, but it does **not** by itself cover the complete visualization/data product. Create a complementary project skill named approximately `production-visualization-agent` with these modules:

- architecture and decision matrix;
- data ingestion/profiling/semantic modeling;
- typed analysis plans, query safety, and validation;
- live UI stream event contract;
- renderer/component registry including Mapbox;
- conversational revision/versioning rules;
- evaluation datasets/gates;
- Logfire/OTel monitoring and privacy;
- security/deployment/release checklists;
- current dependency maturity watchlist.

Reuse, do not duplicate:

- call or reference the project `pydantic-stack-lifecycle` skill for generic lifecycle guidance;
- consume the upstream AntV chart skill package/retrieval API for chart-specific knowledge;
- keep source URLs and version/commit pins in a dependency manifest;
- add an automated review task for upstream breaking changes, archives, license/security changes, and documentation drift;
- keep MCP adapters thin. Runtime business logic remains ordinary typed services and can optionally be exposed through MCP.

### 15.1 Exact AntV skill/context inclusion

AntV skills are **planned dependencies, not yet equivalent to production integration**. Round two selects the following official community assets:

| Asset | Use in this product | Do not use it for |
|---|---|---|
| `chart-visualization` | chart-family recommendation and common chart parameters | production remote rendering or numerical analysis authority |
| `antv-g2-chart` | retrieved G2 v5 constraints/examples for the common-chart adapter | allowing arbitrary generated JavaScript into the browser |
| `antv-s2-expert` | S2 pivot/table configuration, interactions, totals, virtualized cross-analysis | computing unverified aggregates in the renderer |
| `antv-g6-graph` | G6 v5 graph layouts/interactions when relational data is present | ordinary tabular charts or maps |
| `infographic-creator` | reviewed narrative/report/infographic templates and export guidance | sending private data to AntV's public API |
| GPT-Vis package/docs | incremental common-chart rendering from validated vis/JSON specs | host state, revisions, security, data preparation, or truth |
| `@antv/context` | optional local hybrid retrieval over pinned AntV docs/our reviewed adapter notes | automatically trusting live/unversioned documentation |

Runtime integration:

1. Pin `@antv/chart-visualization-skills` by package version and source commit in a dependency manifest.
2. Use its documented `retrieve(query, {library, topK, content: true})` API for G2/G6-specific context. Core constraints are automatically prepended when content is requested. Retrieve the smallest relevant set; do not paste the entire repository into every prompt.
3. Copy no upstream skill into a product system prompt without review. The repository explicitly says its contributions are AI-generated, so every update must pass security, license, compatibility, chart-code, RTL, accessibility, and visual-regression review.
4. Store retrieved context IDs/version with the run trace so a result is reproducible.
5. Add our own reviewed Arabic/RTL, Saudi map, dual-calendar, accessibility, brand-token, exact-render, and streaming rules after upstream context; these product rules win on conflict.
6. Use `@antv/context` only if the package retrieval is insufficient or we need one local index across AntV docs and product guidance.

Developer-agent installation (`npx skills add antvis/chart-visualization-skills`) may help contributors, but it is separate from runtime integration and must not be assumed to be present in deployed containers.

### 15.2 MCP boundary

- [`@antv/mcp-server-antv`](https://github.com/antvis/mcp-server-antv): optional developer/agent documentation and examples.
- [`@antv/mcp-server-chart`](https://github.com/antvis/mcp-server-chart): optional export/external-client adapter. Its default can call a public AntV service, so production must either disable it or point `VIS_REQUEST_SERVER` to a reviewed private GPT-Vis-SSR deployment.
- Internal UI-to-backend streaming remains the typed Vercel AI event contract, not MCP.
- Expose a narrow first-party MCP server later only if other agents need `list_datasets`, `profile_dataset`, `create_visualization`, `revise_artifact`, `get_artifact`, or `export_artifact`. Those tools call the same application services and policies as the UI.
- A2A remains unnecessary until a real remote-agent delegation use case exists. It does not solve browser streaming or artifact state.

### 15.3 Additional community visualization knowledge

Do not install random visualization skills from marketplaces into production. Maintain a curated allowlist with owner, source, license, pinned commit/version, last review date, risk notes, supported library version, and regression suite. Candidates such as Flint's `flint-chart-author` skill may be evaluated in an ADR, but promotion requires the same gates as code dependencies. Community knowledge can advise; product contracts and deterministic validators decide.

## 16. Dependency decisions and watchlist

| Dependency | Decision | Watch item |
|---|---|---|
| Pydantic AI/Validation/Evals/Logfire | Adopt as core Python stack | pin versions; follow V1→V2 migration and UI adapter changes |
| Vercel AI SDK UI | Adopt for web stream transport/state | align adapter and client major versions |
| Ant Design X/Ant Design/ProComponents | Adopt for chat/product/dashboard UI | avoid coupling business state to component internals |
| GPT-Vis | Adopt for common live AI charts | validate production stability and maintain fallback to G2 |
| Microsoft Flint | Post-release evaluation only | new project; chart coverage, RTL/a11y, bundle size, backend fidelity; must not become the universal artifact schema |
| G2 / Ant Design Charts | Adopt for advanced statistical charts | use behind product-level spec adapter |
| S2 | Adopt for pivot/cross-analysis | virtualize and keep result-size limits |
| Mapbox GL JS | Adopt for maps | token, cost, tile/boundary license, sovereignty; keep MapLibre escape hatch |
| react-map-gl | Adopt as controlled React wrapper for Mapbox | align supported Mapbox major version and avoid imperative state drift |
| deck.gl | Optional lazy-loaded spatiotemporal/high-volume overlay | bundle/GPU cost, timestamp precision, only where Mapbox layers are insufficient |
| G6/Graphin | Optional for graph use cases | lazy-load; do not include in baseline bundle |
| X6 | Use only for editable diagrams | not a normal analytics dependency |
| Infographic | Optional export/storytelling | early-stage API; isolate behind adapter |
| AntV AVA | Experimental candidate generator only | never trust confidence score as verification |
| AntV chart MCP | Optional interop/export | default remote renderer is prohibited for sensitive data |
| AntV chart skills | Adopt as retrieved/pinned knowledge dependency | repository warns that contributions are AI-generated; review before updates |
| `@antv/context` | Optional local AntV/product-doc retrieval | index/model size and deterministic versioning; use only when package retrieval is insufficient |
| DuckDB + Arrow/Parquet | Adopt for uploaded/ad-hoc data | strong sandbox and resource controls |
| Ibis | Adopt behind query-compiler interface if prototype confirms coverage | portability gaps; do not expose raw expressions to users |
| SQLGlot | Adopt for AST policy/lineage/diff | parser is not a validator |
| Great Expectations | Adopt for promoted/governed datasets | too heavy for initial arbitrary-upload profiling |
| `hijridate` | Adopt and pin for backend Umm al-Qura conversion | supported range ends at 1500 AH/2077-11-16; conversion version and authoritative fixtures required |
| dbt/MetricFlow | Integrate when customer already uses dbt | hosted Semantic Layer tier requirements |
| WrenAI | Evaluate for governed multi-source context | OSS security/UI boundary and rapidly changing 2026 architecture |
| Vanna | Compatibility only; migrate away | repository archived 2026-03-29 |

## 17. Definition of production-grade completion

The product is not production-grade merely because it renders charts. It is ready only when:

- users can upload/query/revise/publish through the live UI;
- users can render chart-ready data exactly, with no agent or computation, and the product proves that invariant;
- numbers are deterministic, validated, and traceable;
- ambiguous analysis is surfaced rather than guessed;
- every artifact has dataset/source-view and revision lineage; semantic, analysis, and result lineage is mandatory when those modes are used and absent—not fabricated—for exact rendering;
- chart/dashboard/map revisions preserve correct recomputation semantics;
- Hijri/Gregorian and geospatial-temporal views preserve declared calendar, time zone, CRS, geometry, conversion, and boundary provenance;
- the UI renders useful partial artifacts live and clearly distinguishes preview from final;
- all approved models pass the same release gates;
- tenant isolation, query sandboxing, prompt-injection defenses, privacy, audit, and data retention are enforced;
- offline and online evals, observability, alerting, rollback, backup, and incident runbooks are operating;
- library/provider failures degrade gracefully without corrupting or losing verified results.

## 18. Immediate next action

Do not start by building more chart implementations. Start Phase 0 by agreeing on the typed contracts, modes, and event/revision model, then refactor the current POC so that both its direct-render and deterministic-analysis paths produce those contracts. Use two connected vertical slices:

```text
Slice A — exact visualization
CSV upload
→ canonical Parquet + live profile
→ render_only lock + direct field bindings
→ live GPT-Vis scatter/line chart from exact row batches
→ “change it to bars / change the palette”
→ binding/presentation revision, no LLM and no query
→ source fingerprint and no-computation eval + Logfire trace

Slice B — verified visual analysis
same DatasetVersion
→ typed TrendPlan
→ deterministic DuckDB execution
→ verified ResultSet
→ live GPT-Vis line chart
→ “change it to bars” (presentation revision, no requery)
→ “show Riyadh only” (analytical revision, requery)
→ exact eval + Logfire trace
```

These slices prove the hardest product invariants—exact visualization without computation, verified analysis when requested, live rendering, revision semantics, and observability—before expanding the chart catalog or adding more agents.
