"""Insightor mini-agent — a REAL agent loop over the REAL AntV MCP server.

  LLM (via OpenRouter, pydantic-ai)  ──►  @antv/mcp-server-chart (MCP, stdio)
                                              │  VIS_REQUEST_SERVER
                                              ▼
                                    local render service (gpt-vis-ssr)
                                              ▼
                                        out/mcp-*.png

Nothing is mocked: the model decides which chart tool to call, the MCP server
receives the call over the protocol, and the chart is rendered locally so no
data leaves the machine.

Usage:
  export OPENROUTER_API_KEY=sk-or-...
  .venv/bin/python agent/main.py "أي المناطق سجلت أعلى نمو في المعاملات؟"
  .venv/bin/python agent/main.py --check      # verify MCP wiring without an LLM

Env:
  AGENT_MODEL   pydantic-ai model string (default: openrouter:anthropic/claude-opus-4.6;
                any tool-calling model on openrouter.ai/models works)
  RENDER_PORT   local render service port (default 3100)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
RENDER_PORT = int(os.environ.get("RENDER_PORT", "3100"))
MODEL = os.environ.get("AGENT_MODEL", "openrouter:anthropic/claude-opus-4.6")
MCP_SERVER_JS = ROOT / "node_modules/@antv/mcp-server-chart/build/index.js"

# Removed from the MCP tool menu entirely (server-side), so no model can pick
# them: dual-axes charts mislead (two units, one plot), liquid gauges and word
# clouds decorate rather than inform. Override with AGENT_DISABLED_TOOLS.
DISABLED_TOOLS = os.environ.get(
    "AGENT_DISABLED_TOOLS",
    "generate_dual_axes_chart,generate_liquid_chart,generate_word_cloud_chart",
)

INSTRUCTIONS = """\
You are Insightor, a data analyst for executive leaders in an Arabic-speaking government.
You are given the result of a SQL query as CSV text, plus the user's question.

Rules:
1. Compute the numbers you need from the CSV yourself (totals, growth, shares).
2. AGGREGATE before charting: a chart gets at most ~12 categories or ~5 series.
   Never pass raw rows into a chart tool.
3. Call exactly ONE chart tool that best answers the question, with an Arabic
   title and Arabic axis titles. Prefer the simple forms — column, bar, line,
   area, pie, scatter — one measure, one axis.
   EXCEPTION: if the answer is a single number (one KPI, a total, one row) —
   call `show_kpi` instead of any chart tool. A chart with one bar is noise;
   a big number with a label is the correct visualization.
4. Answer in Arabic: one headline sentence with the key number, two or three
   supporting sentences with real figures, then mention the chart you produced.
5. Numbers in your text must come from the CSV — never invent or round beyond
   one decimal.
"""


def show_kpi(value: str, label: str, context: str = "") -> str:
    """Display one headline number as a KPI card instead of a chart.

    Use this when the result is a single figure (a total, one KPI, a one-row
    result). `value` is the formatted number (e.g. "35,300,000"), `label` names
    it in Arabic (e.g. "إجمالي عدد السكان"), `context` optionally adds one short
    comparison or note in Arabic.
    """
    return "ok"


AGENT_TOOLS = [show_kpi]


def start_render_server() -> subprocess.Popen:
    """Launch the private chart renderer (demos/render-server.mjs) and wait for it."""
    log_path = ROOT / "render-server.log"
    log = open(log_path, "w")
    proc = subprocess.Popen(
        ["node", "-r", "./demos/css-noop.cjs", "demos/render-server.mjs"],
        cwd=ROOT,
        env={**os.environ, "PORT": str(RENDER_PORT)},
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    # First-ever run on a machine can be slow: Fontconfig builds its font cache
    # silently (macOS with many fonts: can exceed a minute). Later runs are instant.
    deadline = time.time() + int(os.environ.get("RENDER_TIMEOUT", "150"))
    while time.time() < deadline:
        if proc.poll() is not None:
            break  # node exited — no point waiting out the deadline
        with socket.socket() as s:
            s.settimeout(0.3)
            try:
                s.connect(("127.0.0.1", RENDER_PORT))
                return proc
            except OSError:
                time.sleep(0.3)
    proc.terminate()
    log.flush()
    tail = log_path.read_text(encoding="utf-8", errors="replace")[-2500:] or "(no output)"
    raise RuntimeError(
        f"render server did not come up on port {RENDER_PORT}.\n"
        f"--- {log_path.name} (tail) ---\n{tail}\n"
        "If the log shows a canvas/module error: use Node LTS (22/24) and re-run `npm i`, "
        "or build canvas from source (brew install pkg-config cairo pango libpng jpeg giflib "
        "librsvg && npm rebuild canvas). If there is NO output: the first run may still be "
        "building the system font cache — run `node -r ./demos/css-noop.cjs demos/render-server.mjs` "
        "in the foreground once and wait for 'render server on'; later runs are instant. "
        "RENDER_TIMEOUT env raises this wait."
    )


def make_transport():
    from pydantic_ai.mcp import StdioTransport

    if not MCP_SERVER_JS.exists():
        sys.exit(f"MCP server not found at {MCP_SERVER_JS} — run `npm install` in the repo root first.")
    return StdioTransport(
        command="node",
        args=[str(MCP_SERVER_JS)],
        env={
            **os.environ,
            "VIS_REQUEST_SERVER": f"http://127.0.0.1:{RENDER_PORT}",
            "DISABLED_TOOLS": DISABLED_TOOLS,
        },
    )


async def check_wiring() -> None:
    """No-LLM verification: real MCP handshake, real tool call, real local render."""
    from fastmcp import Client

    async with Client(make_transport()) as client:
        tools = await client.list_tools()
        print(f"MCP OK — {len(tools)} tools exposed by @antv/mcp-server-chart")
        print("  " + ", ".join(sorted(t.name for t in tools)[:8]) + ", …")
        result = await client.call_tool(
            "generate_column_chart",
            {
                "data": [
                    {"category": "الرياض", "value": 660500},
                    {"category": "مكة المكرمة", "value": 402000},
                    {"category": "الشرقية", "value": 370800},
                ],
                "title": "فحص الاتصال — عبر بايدانتك",
                "axisXTitle": "المنطقة",
                "axisYTitle": "المعاملات",
            },
        )
        url = result.content[0].text if result.content else "<no content>"
        print(f"tool call OK — chart at {url}")
    print("wiring verified: pydantic-ai transport → MCP server → local renderer")


async def run_agent(question: str) -> None:
    from pydantic_ai import Agent
    from pydantic_ai.mcp import MCPToolset

    csv_text = (ROOT / "data/monthly_transactions.csv").read_text(encoding="utf-8")
    agent = Agent(MODEL, instructions=INSTRUCTIONS, tools=AGENT_TOOLS, toolsets=[MCPToolset(make_transport())])

    before = {p.name for p in OUT.glob("*.png")} if OUT.exists() else set()
    print(f"model: {MODEL}\nquestion: {question}\n--- running agent ---")
    result = await agent.run(f"SQL result (CSV):\n\n{csv_text}\n\nQuestion: {question}")

    print(result.output)
    print("\n--- tool calls made ---")
    for msg in result.all_messages():
        for part in getattr(msg, "parts", []):
            kind = getattr(part, "part_kind", "")
            if kind == "tool-call":
                print(f"  → {part.tool_name}")
            elif kind == "tool-return":
                print(f"  ← {str(part.content)[:120]}")
    new = sorted({p.name for p in OUT.glob("*.png")} - before)
    if new:
        print("\ncharts rendered locally: " + ", ".join(f"out/{n}" for n in new))
    usage = result.usage
    print(f"\ntokens: {usage.input_tokens} in / {usage.output_tokens} out")


def main() -> None:
    parser = argparse.ArgumentParser(description="Insightor agent over the AntV chart MCP server")
    parser.add_argument("question", nargs="?", default="أي المناطق سجلت أعلى نمو في المعاملات خلال 2025؟ وما حجم الفارق؟")
    parser.add_argument("--check", action="store_true", help="verify MCP wiring without calling an LLM")
    args = parser.parse_args()

    if not args.check and not os.environ.get("OPENROUTER_API_KEY") and MODEL.startswith("openrouter:"):
        sys.exit("Set OPENROUTER_API_KEY (or AGENT_MODEL for a different provider). Use --check to test wiring without a key.")

    renderer = start_render_server()
    try:
        asyncio.run(check_wiring() if args.check else run_agent(args.question))
    finally:
        renderer.terminate()


if __name__ == "__main__":
    main()
