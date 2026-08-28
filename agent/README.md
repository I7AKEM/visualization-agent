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

```sh
# from the repo root — Node deps (MCP server + renderer) must already be installed
npm install

# Python side
uv venv agent/.venv
VIRTUAL_ENV=agent/.venv uv pip install -r agent/requirements.txt
```

## Verify the wiring — no API key needed

Real MCP handshake, real tool call, real local render; only the LLM is absent:

```sh
agent/.venv/bin/python agent/main.py --check
```

## Run it for real

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
