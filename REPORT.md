# AntV for Insightor — research + hands-on test results

*Research date: 2026-08-28. Everything in "What I tested" was actually run in this repo — the code and the rendered charts are committed here.*

## The short answer

AntV is not one product — it is a family of about ten visualization libraries from Ant Group (the Alipay company). Most of them are **not** relevant to Insightor. Three of them are almost purpose-built for what you are doing, and they work together as one stack:

1. **mcp-server-chart** — a ready-made bridge that lets Claude (or any AI assistant) say "draw a column chart of this data" and get back a finished chart image. 27 chart tools out of the box.
2. **gpt-vis-ssr** — the piece that actually turns a chart request into a PNG image on *your own server*. This is what your "Arabic visualization" tool should be built on. Tested here with Arabic government data: **Arabic text renders correctly with zero special configuration** once an Arabic font is installed on the server.
3. **AVA** — an "automatic analyst" library. You give it the table your SQL tool produced, and it finds the stories in it by itself — trends, spikes, outliers, dominant categories — each with a confidence score. This is the difference between a chatbot that draws charts and an assistant that tells a minister *what changed and why it matters*.

One serious warning: **by default, mcp-server-chart sends your data to Alipay's public cloud in China to render the chart.** For government data that is a hard no. The fix is one environment variable (`VIS_REQUEST_SERVER`) pointing at your own renderer — I built and tested that fully-local setup in this repo, and no data leaves the machine.

---

## The AntV family, in plain words

| Project | What it really is | Does Insightor need it? |
|---|---|---|
| **G2** | The chart engine — bars, lines, pies, etc. Everything else charts-related is built on top of it. | Indirectly — it powers gpt-vis-ssr. You rarely touch it directly. |
| **gpt-vis-ssr** | Turns a simple chart description (JSON) into a PNG on a Node server. No browser needed. | **Yes — the core of your visualization tool.** |
| **GPT-Vis** | React components that show charts *inside a chat stream*, while the AI is still typing. Same chart descriptions as above. | Yes, if Insightor has a web chat UI. Charts become interactive instead of static images. |
| **mcp-server-chart** | An MCP server (the standard way to give Claude extra tools) exposing 27 "generate_X_chart" tools. | **Yes — the fastest way to test, and a solid production path.** |
| **AVA** | Automatic analysis: finds trends/outliers/spikes in a table and recommends which chart type fits the data. | **Yes — the "insight brain" Insightor is missing.** |
| **S2** | Pivot tables (like Excel pivot) as a component — millions of rows, drill-down. | Later. Executives love drill-down tables; good phase-2 feature. |
| **L7** | Maps — data on geography (regions, points, flows). | Careful. Its map tools in mcp-server-chart only cover China and use Chinese basemap services. For Saudi/Gulf regional maps you'd use L7 with your own map tiles, or another mapping stack. |
| **G6** | Network diagrams — who is connected to whom. | Rarely, for executive KPIs. Skip for now. |
| **X6** | A diagram *editor* (draw flowcharts by hand, like draw.io). | No. |
| **F2** | Charts optimized for mobile apps. | Only if you build a native mobile app. |
| **Infographic** | New 2025 project, 6.4k stars: AI-generated infographic pages ("bring words to life"). Built for LLMs, ~200 templates. | **Watch it.** Early stage (v0.2.x), SVG output. Could become the "one-page visual brief for the minister" generator. |
| **Ant Design Charts / Graphin** | React wrappers around G2/G6 for normal (non-AI) dashboards. | Only for hand-built dashboard pages. |
| **G2Plot, g2-react, G6VP** | Older generations — deprecated or archived. | **No. Don't adopt anything from these.** |

So the "overlapping projects" impression is right — G2Plot vs Ant Design Charts vs G2, G6 vs Graphin vs X6 — but the overlap disappears once you know the rule: **G2 is the engine, the AI-era layer is GPT-Vis + gpt-vis-ssr + mcp-server-chart + AVA, and everything else is either a wrapper, a specialty (tables/maps/networks/mobile), or deprecated.**

---

## What I tested in this repo (all passed)

### Test 1 — Arabic charts rendered from a CSV, server-side
`demos/01-render-charts.mjs` reads `data/monthly_transactions.csv` (monthly digital-service transactions for 5 Saudi regions, in Arabic) and renders 4 chart types. Results in `out/`:

- Arabic is **fully shaped and connected** (not broken letters, not boxes) in titles, axis titles, category labels, legends, and pie label lines — including mixed Arabic/numbers ("لعام 2025") which the text engine orders correctly.
- The only requirement: an Arabic font installed on the server (`fonts/` + fontconfig — see README). No AntV configuration at all.
- Dark theme works the same.

### Test 2 — automatic insights from the same CSV
`demos/02-insights.mjs` runs AVA over the raw rows. Without being told what to look for, it found: the strong steady growth of الرياض (confidence 1.0), the June spike (Hajj season in the test data) as a time-series outlier, and الرياض as the dominant region month after month. It also recommended chart types: line/area for the monthly series, pie/donut/column for the regional totals.

Two honest caveats: its written summaries come out in English (structured JSON — perfect input for Claude to phrase in Arabic), and with default settings it also reports weak "insights" (it called a nearly-flat region an increasing trend), so you filter by its significance score.

### Test 3 — the Claude integration, end-to-end and fully private
`demos/03-mcp-e2e.mjs` starts a **local** render service (`demos/render-server.mjs`, ~60 lines wrapping gpt-vis-ssr) and then talks to `@antv/mcp-server-chart` over the real MCP protocol exactly like Claude would: handshake → list tools (27) → call `generate_column_chart` and `generate_line_chart` with Arabic data. The server returned URLs served by the local renderer; the PNGs are in `out/mcp-*.png`. **Zero traffic to Alipay's cloud.**

### Gotchas found (so your team doesn't rediscover them)
1. **Data sovereignty:** default rendering endpoint is `https://antv-studio.alipay.com/api/gpt-vis`. Always set `VIS_REQUEST_SERVER` to your own service in any government deployment. The protocol is trivial: POST of the chart spec, respond `{ "success": true, "resultObj": "<image url>" }`.
2. **Node quirk:** `@antv/s2` (pulled in by gpt-vis-ssr) requires `.css` files, which plain Node rejects. Preload `demos/css-noop.cjs` (`node -r ./demos/css-noop.cjs ...`). One line.
3. **RTL polish is on you:** rendering is correct, but layout stays left-to-right — titles anchor left (an Arabic reader expects right), legend items run left-to-right, and horizontal bars grow left-to-right. Readable and correct, but a truly RTL-first product would mirror these. Digits render as 1234 (Western), which is standard in Gulf government dashboards anyway.
4. **Default labels are chatty:** AntV labels every data point; with 5 series × 12 months that's cluttered. For executive output, thin the labels (or aggregate before charting — an executive rarely needs 60 labeled points).
5. **Chart menu discipline:** the 27 tools include types you should quietly not use for executives (word clouds, liquid gauges, dual-axis charts — the latter routinely mislead readers). Constrain the agent to a vetted subset: line, area, column, bar, pie/donut, table.

---

## What this means for Insightor — recommended architecture

Keep Vanna 2.0 exactly where it is. The pipeline becomes:

```
question (Arabic) → Vanna 2.0 → SQL → result table (CSV)
                                         │
        ┌────────────────────────────────┼──────────────────────────┐
        ▼                                ▼                          ▼
  AVA insight scan                chart choice               self-hosted renderer
  (trends, spikes,          (AVA advisor ranks types;       (gpt-vis-ssr behind a
   outliers + scores)        Claude picks + titles it        tiny HTTP service —
        │                    in Arabic)                      the render-server.mjs
        ▼                                                    pattern in this repo)
  Claude writes the                                                 │
  executive summary                                                 ▼
  in Arabic from the                                          PNG for chat, PDF
  structured facts                                            brief, email, WhatsApp
```

Because Vanna is Python and AntV is JavaScript, the clean seam is HTTP: the renderer runs as a small Node sidecar service (or you keep mcp-server-chart in front of it so Claude calls it directly as a tool). Your existing "Arabic visualization" tool then shrinks to: build the chart spec, POST it, attach the PNG.

**Why this beats a hand-rolled matplotlib/Plotly tool for your use case:**
- The chart spec is tiny and LLM-friendly — designed so a model can emit it reliably.
- One spec renders three ways: PNG on the server (briefings), interactive in the chat UI (GPT-Vis React), or through Claude via MCP — same look everywhere.
- Arabic just works (with the font installed), which is exactly the part matplotlib makes painful (bidi/shaping).
- AVA adds the layer executives actually pay attention to: "transactions in مكة المكرمة spiked 79% in June" — surfaced automatically, verified by an algorithm, not hallucinated.

**Executive-leader specifics worth building in:**
- Lead every answer with the headline number and the auto-detected change, not the chart.
- One chart per answer, aggregated (quarters/regions), max ~2 series direct-labeled; details on request.
- Fixed brand palette + fixed region colors across all charts (same region = same color everywhere), set via the spec's `style.palette` — never let each chart pick its own.
- Everything exportable: the PNG pipeline here is already brief/print-ready (renders at 3× resolution).

## Suggested next steps

1. Stand up `render-server.mjs` (hardened: auth, size limits, font baked into the image/container) as the private chart service.
2. Rewrite Insightor's visualization tool to emit gpt-vis specs and call that service.
3. Add an "insight scan" step after SQL using AVA (Node sidecar endpoint, same service) and feed its JSON to the model for the Arabic summary.
4. In your own Claude environment, add the MCP server to test conversationally:
   `claude mcp add antv-charts --env VIS_REQUEST_SERVER=https://charts.internal.example -- npx -y @antv/mcp-server-chart`
5. Phase 2: GPT-Vis React in the chat UI (interactive charts), S2 pivot tables for drill-down, and keep an eye on **Infographic** for auto-generated one-page visual briefs.
