# Insightor mini-agent — real LLM × real MCP × private rendering

A ~150-line [Pydantic AI](https://ai.pydantic.dev) agent that answers a question
about a SQL result (CSV) by **calling the real `@antv/mcp-server-chart` over the
MCP protocol**, with charts rendered by the **local** gpt-vis-ssr service so no
data leaves the machine. Nothing is mocked.

```
you ──question──► pydantic-ai Agent (LLM via OpenRouter)
                        │  decides + calls generate_*_chart over MCP (stdio)
                        ▼
              @antv/mcp-server-chart ──POST──► local render server ──► out/mcp-*.png
```

## Setup (once)

Needs **Python 3.10+** (3.11+ recommended — what this was tested on) and Node 20+.
On macOS the system `python3` is often too old — `brew install python@3.12` first.

```sh
# from the repo root — Node deps (MCP server + renderer) must already be installed
npm install

# Python side (plain venv; or use uv if you have it)
python3.12 -m venv agent/.venv          # any python >= 3.10 works
agent/.venv/bin/pip install --upgrade pip
agent/.venv/bin/pip install -r agent/requirements.txt

# fonts — Linux: cp fonts/*.ttf ~/.local/share/fonts/ && fc-cache -f
#         macOS: cp fonts/*.ttf ~/Library/Fonts/   (optional; mac has Arabic fonts)
```

## Verify the wiring — no API key needed

Real MCP handshake, real tool call, real local render; only the LLM is absent:

```sh
agent/.venv/bin/python agent/main.py --check
```

## Web UI — watch the agent live

```sh
export OPENROUTER_API_KEY=sk-or-...
agent/.venv/bin/python agent/web.py     # → open http://127.0.0.1:8300
```

Paste or upload any CSV, ask a question, hit **Run agent**, and watch the live
feed: the model's text streams in, every MCP tool call appears with its
arguments, and each chart renders **live and interactive in the page** (hover
for tooltips) the moment its tool call streams in — the same G2 engine GPT-Vis
uses, served from local `node_modules` (no CDN, works offline). The PNG from
the private renderer stays available as an export link; chart types without a
live mapping (line, area, column, bar, pie, scatter have one) fall back to it.
**Check MCP wiring** works with no API key; typing `test` as the model runs the
loop with a stub LLM (MCP calls and rendering still real). No extra Python
deps — the UI runs on starlette/uvicorn, which pydantic-ai already installs.

## Tracks — fast vs smart

The UI has a **Track** switch:

- **Smart (LLM)** — the full agent: model reads the handoff, decides, calls MCP
  tools, streams the Arabic answer. Seconds; best quality.
- **Fast (planner)** — a small model DECIDES, code EXECUTES: one single-shot
  structured-output call (schema + 5 sample rows + question, never the full
  CSV) returns a validated plan — chart form, columns, equality filters,
  top-N, titles — then code filters/aggregates/renders and templates the
  Arabic numbers. Plans are cached by (schema + intent + question), so repeat
  questions plan in 0 ms. The old shape-based heuristic survives only as a
  labeled last-resort fallback. `PLANNER_MODEL` env picks the planner
  (default `openrouter:anthropic/claude-haiku-4.5` — change the slug if
  OpenRouter renames it). `agent/fast_track.py`.
- **Both** — fast result appears instantly, then the smart track streams in
  behind it. The production pattern when latency matters: the executive sees a
  chart in half a second and the considered narrative arrives after.

Every run ends with `done · N ms` so tracks can be compared directly.

## Run it for real (CLI)

```sh
export OPENROUTER_API_KEY=sk-or-...          # openrouter.ai/keys
agent/.venv/bin/python agent/main.py "أي المناطق سجلت أعلى نمو في المعاملات؟"
```

The agent receives `data/monthly_transactions.csv` as the "SQL result", answers
in Arabic with computed numbers, calls one chart tool through MCP, and the
rendered PNG lands in `out/`. The run log shows every tool call and the token
usage.

## Configuration

| Env | Default | Notes |
|---|---|---|
| `OPENROUTER_API_KEY` | — | required for real runs with the default model |
| `AGENT_MODEL` | `openrouter:anthropic/claude-opus-4.6` | any tool-calling model slug from openrouter.ai/models, e.g. `openrouter:anthropic/claude-sonnet-4.5`. Direct providers work too (`anthropic:claude-opus-5` with `ANTHROPIC_API_KEY`). |
| `RENDER_PORT` | `3100` | port for the private renderer |

If the default model slug 404s (OpenRouter renames models), pick any current
Claude slug from openrouter.ai/models and set `AGENT_MODEL`.
