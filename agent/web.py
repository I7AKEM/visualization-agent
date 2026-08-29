"""Local web UI for the Insightor MCP agent.

Serves a single page where you paste/upload a CSV and a question, then streams
the agent's activity live: model text as it is generated, every MCP tool call
with its arguments, and each chart the moment the local renderer produces it.

  uv run --python agent/.venv/bin/python agent/web.py     # or:
  agent/.venv/bin/python agent/web.py                     # → http://127.0.0.1:8300

Uses the same core as main.py — real LLM (OpenRouter), real @antv/mcp-server-chart
over stdio MCP, private local rendering. `AGENT_MODEL=test` (or typing `test` in
the model box) runs the loop with pydantic-ai's stub model — real MCP, no LLM —
for trying the UI without an API key.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
import time
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.routing import Route

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fast_track  # noqa: E402  (the no-LLM deterministic track)
import main as core  # noqa: E402  (shared transport, renderer, instructions)

UI_PORT = int(os.environ.get("UI_PORT", "8300"))
run_lock = asyncio.Lock()


async def index(request):
    return FileResponse(HERE / "ui.html")


async def sample(request):
    return FileResponse(core.ROOT / "data/monthly_transactions.csv", media_type="text/csv")


async def g2js(request):
    # Serve G2 from node_modules: no CDN dependency, works offline/air-gapped,
    # and the browser engine version always matches the server-side renderer's.
    path = core.ROOT / "node_modules/@antv/g2/dist/g2.min.js"
    if not path.exists():
        return JSONResponse({"error": "run npm install first"}, status_code=404)
    return FileResponse(path, media_type="text/javascript")


async def health(request):
    needs_key = core.MODEL.startswith("openrouter:")
    return JSONResponse({
        "model": core.MODEL,
        "has_key": bool(os.environ.get("OPENROUTER_API_KEY")) or not needs_key,
        "mcp_server": core.MCP_SERVER_JS.exists(),
    })


async def check(request):
    """Keyless wiring check: real MCP handshake + one real tool call."""
    from fastmcp import Client

    async with Client(core.make_transport()) as client:
        tools = await client.list_tools()
        result = await client.call_tool(
            "generate_column_chart",
            {
                "data": [
                    {"category": "الرياض", "value": 660500},
                    {"category": "مكة المكرمة", "value": 402000},
                    {"category": "الشرقية", "value": 370800},
                ],
                "title": "فحص الاتصال",
                "axisXTitle": "المنطقة",
                "axisYTitle": "المعاملات",
            },
        )
        url = result.content[0].text if result.content else None
    return JSONResponse({"tools": len(tools), "names": sorted(t.name for t in tools), "sample_chart": url})


def build_agent(model_str: str):
    from pydantic_ai import Agent
    from pydantic_ai.mcp import MCPToolset

    if model_str == "test":
        from pydantic_ai.models.test import TestModel

        model = TestModel(call_tools=["generate_column_chart", "generate_line_chart", "show_kpi"])
    else:
        model = model_str
    return Agent(model, instructions=core.INSTRUCTIONS, tools=core.AGENT_TOOLS, toolsets=[MCPToolset(core.make_transport())])


async def run(request):
    body = await request.json()
    csv_text = (body.get("csv") or "").strip()
    question = (body.get("question") or "").strip() or "حلّل البيانات وقدّم أبرز النتائج للقيادة."
    model_str = (body.get("model") or core.MODEL).strip()
    handoff = {k: (body.get(k) or "").strip() for k in ("enriched", "intent", "sql", "notes")}
    track = (body.get("track") or "smart").strip()  # fast | smart | both

    if not csv_text:
        return JSONResponse({"error": "CSV is empty"}, status_code=400)
    if len(csv_text) > 300_000:
        return JSONResponse(
            {"error": "CSV is over 300 KB — too large to hand an LLM. Aggregate it first (that is the production pattern)."},
            status_code=400,
        )

    def line(obj) -> str:
        return json.dumps(obj, ensure_ascii=False) + "\n"

    async def smart_events():
        t0 = time.perf_counter()
        yield {"type": "status", "message": f"smart track: agent starting — model: {model_str}"}
        agent = build_agent(model_str)
        rows = csv_text.count("\n")
        yield {"type": "status", "message": f"CSV handed to the model: ~{rows} rows, {len(csv_text)} chars"}
        provided = [k for k, v in handoff.items() if v]
        if provided:
            yield {"type": "status", "message": "handoff from data agent: " + ", ".join(provided)}
        prompt = core.build_prompt(csv_text, question, **handoff)
        async with agent.run_stream_events(prompt) as events:
            async for ev in events:
                kind = type(ev).__name__
                if kind == "FunctionToolCallEvent":
                    args = ev.part.args
                    if not isinstance(args, str):
                        args = json.dumps(args, ensure_ascii=False)
                    # full args — the UI renders the chart from them; it truncates for display itself
                    yield {"type": "tool_call", "tool": ev.part.tool_name, "args": args[:200_000]}
                elif kind == "FunctionToolResultEvent":
                    yield {"type": "tool_result", "tool": ev.part.tool_name, "content": str(ev.part.content)[:600]}
                elif kind == "PartStartEvent" and getattr(ev.part, "part_kind", "") == "text":
                    if ev.part.content:
                        yield {"type": "text", "delta": ev.part.content}
                elif kind == "PartDeltaEvent":
                    delta = getattr(ev.delta, "content_delta", None)
                    if delta:
                        yield {"type": "text", "delta": delta}
                elif kind == "AgentRunResultEvent":
                    usage = ev.result.usage
                    yield {"type": "done", "input_tokens": usage.input_tokens,
                           "output_tokens": usage.output_tokens,
                           "ms": round((time.perf_counter() - t0) * 1000)}

    async def gen():
        if run_lock.locked():
            yield line({"type": "error", "message": "another run is already in progress"})
            return
        async with run_lock:
            try:
                if track in ("fast", "both"):
                    async for e in fast_track.fast_events(csv_text, question, handoff,
                                                          f"http://127.0.0.1:{core.RENDER_PORT}"):
                        yield line(e)
                if track in ("smart", "both"):
                    async for e in smart_events():
                        yield line(e)
            except Exception as e:  # surfaced in the UI, not swallowed
                yield line({"type": "error", "message": f"{type(e).__name__}: {e}"})

    return StreamingResponse(gen(), media_type="application/x-ndjson")


@contextlib.asynccontextmanager
async def lifespan(app):
    renderer = core.start_render_server()
    try:
        yield
    finally:
        renderer.terminate()


app = Starlette(
    routes=[
        Route("/", index),
        Route("/api/sample", sample),
        Route("/vendor/g2.min.js", g2js),
        Route("/api/health", health),
        Route("/api/check", check, methods=["POST"]),
        Route("/api/run", run, methods=["POST"]),
    ],
    lifespan=lifespan,
)

if __name__ == "__main__":
    print(f"Insightor agent UI → http://127.0.0.1:{UI_PORT}")
    uvicorn.run(app, host="127.0.0.1", port=UI_PORT, log_level="warning")
