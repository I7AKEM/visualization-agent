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
arguments, and each chart shows up the moment the local renderer produces it.
**Check MCP wiring** works with no API key; typing `test` as the model runs the
loop with a stub LLM (MCP calls and rendering still real). No extra Python
deps — the UI runs on starlette/uvicorn, which pydantic-ai already installs.

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
