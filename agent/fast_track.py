"""Fast track v2 — planner-based: a small model DECIDES, code EXECUTES.

Pure heuristics make stupid chart choices because chart choice depends on
meaning, not column shapes. This track keeps intelligence but strips the
latency sources: ONE single-shot structured-output call to a fast model gets
only the schema + a few sample rows + the question (never the full CSV) and
returns a validated plan. Code then filters, aggregates, renders, and writes
the numbers. Decisions are cached by (schema + intent + question), so repeat
questions plan in ~0 ms. The old heuristic survives only as a last-resort
fallback when the planner is unavailable or returns an invalid plan.

Emits the same event dicts the web UI already understands:
  status / tool_call / tool_result / text / done
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import time
from pathlib import Path
from typing import Literal, Optional

import httpx
from pydantic import BaseModel, Field

PLANNER_MODEL = os.environ.get("PLANNER_MODEL", "openrouter:anthropic/claude-haiku-4.5")
CACHE_FILE = Path(__file__).resolve().parent / ".plan_cache.json"

AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
DATE_RE = re.compile(r"^\d{4}([-/]\d{1,2}){0,2}$|^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}$")
TIME_NAMES = re.compile(r"^(month|date|year|week|day|quarter|شهر|سنة|تاريخ|ربع|أسبوع|يوم)$", re.I)


# ---------------------------------------------------------------- the plan --
class Plan(BaseModel):
    """What to draw and from which columns — the entire decision, nothing else."""

    tool: Literal["column", "bar", "line", "area", "pie", "scatter", "kpi"]
    y: str = Field(description="the measure column (numeric). For agg=count it may be any column.")
    x: Optional[str] = Field(None, description="category or time column for the x axis; null for kpi")
    group: Optional[str] = Field(None, description="optional series/split column (keep under ~8 series)")
    filter: dict[str, str] = Field(default_factory=dict, description="equality filters, column -> value, ONLY when the question restricts the data")
    agg: Literal["sum", "mean", "count"] = "sum"
    top_n: int = Field(12, ge=1, le=30)
    title: str = Field(description="chart title in the question's language")
    axis_x_title: str = ""
    axis_y_title: str = ""
    kpi_label: str = Field("", description="for tool=kpi: the label under the number")


PLANNER_INSTRUCTIONS = """\
You plan ONE visualization for a government-executive data assistant. You get a
column schema, a few sample rows, the user's question, and optionally an intent
and the SQL that produced the data. Return only the plan.

Rules:
- Use EXACT column names from the schema. Never invent columns.
- y must be a numeric column (unless agg=count). x is the category/time column.
- Use `filter` only when the question restricts the data (a specific month,
  region, service...). Equality filters only.
- tool=kpi when a single number answers the question (totals, one row).
- Prefer simple forms. line/area for change over time; column/bar for
  comparison or ranking; pie only for shares across <= 6 categories.
- Title and axis titles in the question's language (Arabic question -> Arabic titles).
"""


# ------------------------------------------------------------- small utils --
def _num(s):
    s = str(s).strip().translate(AR_DIGITS).replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def fmt(n: float) -> str:
    return f"{n:,.1f}".rstrip("0").rstrip(".") if n % 1 else f"{int(n):,}"


def profile(rows: list[dict]) -> dict:
    cols = {}
    for name in rows[0].keys():
        vals = [r[name] for r in rows[:2000] if str(r[name]).strip() != ""]
        nums = sum(1 for v in vals if _num(v) is not None)
        dates = sum(1 for v in vals if DATE_RE.match(str(v).strip().translate(AR_DIGITS)))
        kind = "text"
        if vals and dates / len(vals) > 0.85:
            kind = "date"
        elif vals and nums / len(vals) > 0.9:
            kind = "number"
        cols[name] = {"kind": kind, "distinct": len({str(v) for v in vals}),
                      "samples": [str(v) for v in vals[:3]]}
    return cols


# ------------------------------------------------------------------- cache --
def _load_cache() -> dict:
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


_CACHE = _load_cache()


def cache_key(cols: dict, question: str, intent: str) -> str:
    schema = "|".join(f"{c}:{p['kind']}" for c, p in sorted(cols.items()))
    q = re.sub(r"\s+", " ", question.strip().lower())
    return hashlib.sha256(f"{schema}\n{intent.strip().lower()}\n{q}".encode()).hexdigest()[:16]


def _cache_store(key: str, plan: Plan) -> None:
    _CACHE[key] = plan.model_dump()
    try:
        CACHE_FILE.write_text(json.dumps(_CACHE, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass


# ----------------------------------------------------------------- planner --
async def run_planner(cols: dict, sample_rows: list[dict], question: str, handoff: dict) -> Plan:
    from pydantic_ai import Agent

    if PLANNER_MODEL == "test":  # sandbox/no-key mode: exercises the fallback path
        from pydantic_ai.models.test import TestModel

        model = TestModel()
    else:
        model = PLANNER_MODEL
    agent = Agent(model, output_type=Plan, instructions=PLANNER_INSTRUCTIONS)
    payload = {
        "columns": {c: {"kind": p["kind"], "distinct": p["distinct"], "samples": p["samples"]} for c, p in cols.items()},
        "sample_rows": sample_rows[:5],
        "question": question,
        "intent": handoff.get("intent") or None,
        "enriched_question": handoff.get("enriched") or None,
        "sql": handoff.get("sql") or None,
    }
    result = await agent.run(json.dumps(payload, ensure_ascii=False))
    return result.output


def validate_plan(plan: Plan, cols: dict) -> list[str]:
    errs = []
    names = set(cols)
    for field in ("y", "x", "group"):
        v = getattr(plan, field)
        if v is not None and v not in names:
            errs.append(f"{field}={v!r} is not a column")
    for c in plan.filter:
        if c not in names:
            errs.append(f"filter column {c!r} does not exist")
    if plan.agg != "count" and plan.y in names and cols[plan.y]["kind"] != "number":
        errs.append(f"y={plan.y!r} is not numeric")
    if plan.tool != "kpi" and plan.x is None:
        errs.append("x is required unless tool=kpi")
    if plan.tool == "scatter" and (plan.x not in names or cols[plan.x]["kind"] != "number"):
        errs.append("scatter needs a numeric x")
    return errs


def heuristic_plan(cols: dict, question: str, intent: str, n_rows: int) -> Plan:
    """Last-resort fallback only — shape-based guessing, known to be naive."""
    numbers = [c for c, p in cols.items() if p["kind"] == "number"]
    dates = [c for c in cols if cols[c]["kind"] == "date" or TIME_NAMES.match(c)]
    texts = [c for c, p in cols.items() if p["kind"] == "text" and 2 <= p["distinct"] <= 60 and c not in dates]
    y = numbers[0] if numbers else next(iter(cols))
    time_col = dates[0] if dates else None
    dim = min(texts, key=lambda c: cols[c]["distinct"]) if texts else None
    if intent == "kpi" or n_rows == 1 or (not time_col and not dim):
        tool, x = "kpi", None
    elif time_col:
        tool, x = "line", time_col
    else:
        tool, x = "column", dim
    return Plan(tool=tool, y=y, x=x, group=dim if (tool == "line" and dim) else None,
                title=question[:70] if question else y, axis_x_title=x or "", axis_y_title=y,
                kpi_label=f"إجمالي {y}")


# --------------------------------------------------------------- execution --
def execute_plan(plan: Plan, rows: list[dict]) -> tuple[dict | None, dict | None, list[str]]:
    """Returns (chart_spec, kpi_args, sentences). Numbers computed here, never by a model."""
    if plan.filter:
        rows = [r for r in rows
                if all(str(r.get(c, "")).strip() == str(v).strip() for c, v in plan.filter.items())]
    if not rows:
        return None, None, ["لا توجد صفوف مطابقة للفلتر المطلوب."]

    def val(r):
        return 1.0 if plan.agg == "count" else _num(r.get(plan.y))

    sentences: list[str] = []
    if plan.tool == "kpi":
        vals = [v for r in rows if (v := val(r)) is not None]
        total = sum(vals) / len(vals) if plan.agg == "mean" and vals else sum(vals)
        kpi = {"value": fmt(total), "label": plan.kpi_label or f"إجمالي {plan.y}", "context": plan.title}
        sentences.append(f"{kpi['label']}: {kpi['value']}.")
        return None, kpi, sentences

    if plan.tool == "scatter":
        data = [{"x": xv, "y": yv} for r in rows[:1500]
                if (xv := _num(r.get(plan.x))) is not None and (yv := _num(r.get(plan.y))) is not None]
        spec = {"type": "scatter", "data": data, "title": plan.title,
                "axisXTitle": plan.axis_x_title or plan.x, "axisYTitle": plan.axis_y_title or plan.y}
        sentences.append(f"مخطط انتشار لـ {len(data)} نقطة بين {plan.x} و{plan.y}.")
        return spec, None, sentences

    # aggregate y by x (and group)
    acc, order = {}, []
    for r in rows:
        v = val(r)
        if v is None:
            continue
        k = (str(r.get(plan.x, "")).strip(), str(r.get(plan.group, "")).strip() if plan.group else None)
        if k not in acc:
            acc[k] = []
            order.append(k)
        acc[k].append(v)
    agg = {k: (sum(vs) / len(vs) if plan.agg == "mean" else sum(vs)) for k, vs in acc.items()}

    if plan.tool in ("line", "area"):
        if plan.group:
            g_tot = {}
            for (x, g), v in agg.items():
                g_tot[g] = g_tot.get(g, 0) + v
            keep = set(sorted(g_tot, key=g_tot.get, reverse=True)[:8])
            data = sorted([{"time": x, "value": round(v, 2), "group": g}
                           for (x, g), v in agg.items() if g in keep], key=lambda d: d["time"])
            top_series = sorted([d for d in data if d["group"] == max(g_tot, key=g_tot.get)], key=lambda d: d["time"])
        else:
            data = sorted([{"time": x, "value": round(v, 2)} for (x, _), v in agg.items()], key=lambda d: d["time"])
            top_series = data
        spec = {"type": plan.tool, "data": data, "title": plan.title,
                "axisXTitle": plan.axis_x_title or plan.x, "axisYTitle": plan.axis_y_title or plan.y}
        if len(top_series) >= 2:
            a, b = top_series[0]["value"], top_series[-1]["value"]
            pct = (b - a) / a * 100 if a else 0
            who = f"{top_series[0].get('group')}: " if plan.group else ""
            sentences.append(f"{who}{plan.y} {'ارتفع' if pct >= 0 else 'انخفض'} من {fmt(a)} إلى {fmt(b)} ({'+' if pct >= 0 else ''}{pct:.1f}%).")
        return spec, None, sentences

    # column / bar / pie
    items = sorted([(x, v) for (x, _), v in agg.items()], key=lambda t: -t[1])
    if len(items) > plan.top_n:
        rest = sum(v for _, v in items[plan.top_n:])
        items = items[:plan.top_n] + [("أخرى", rest)]
    data = [{"category": k, "value": round(v, 2)} for k, v in items]
    spec = {"type": plan.tool if plan.tool in ("column", "bar", "pie") else "column",
            "data": data, "title": plan.title}
    if spec["type"] != "pie":
        spec.update({"axisXTitle": plan.axis_x_title or plan.x, "axisYTitle": plan.axis_y_title or plan.y})
    total = sum(d["value"] for d in data)
    if data and total:
        top = data[0]
        sentences.append(f"{top['category']} في الصدارة بقيمة {fmt(top['value'])} ({top['value']/total*100:.1f}% من الإجمالي البالغ {fmt(total)}).")
        if len(data) > 1:
            sentences.append(f"أدنى قيمة: {data[-1]['category']} ({fmt(data[-1]['value'])}).")
    return spec, None, sentences


# ------------------------------------------------------------ event stream --
async def fast_events(csv_text: str, question: str, handoff: dict, render_url: str):
    t0 = time.perf_counter()
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    if not rows:
        yield {"type": "error", "message": "fast track: could not read the CSV"}
        return
    cols = profile(rows)
    intent = handoff.get("intent", "")

    plan, source, plan_ms = None, None, 0
    key = cache_key(cols, question, intent)
    if key in _CACHE:
        try:
            plan, source = Plan.model_validate(_CACHE[key]), "cache"
        except Exception:
            plan = None
    if plan is None:
        tp = time.perf_counter()
        try:
            plan = await run_planner(cols, rows[:5], question, handoff)
            plan_ms = round((time.perf_counter() - tp) * 1000)
            errs = validate_plan(plan, cols)
            if errs:
                yield {"type": "status", "message": "planner returned an invalid plan (" + "; ".join(errs) + ") → heuristic fallback"}
                plan, source = None, None
            else:
                source = "planner"
                _cache_store(key, plan)
        except Exception as e:
            plan_ms = round((time.perf_counter() - tp) * 1000)
            yield {"type": "status", "message": f"planner unavailable ({type(e).__name__}) → heuristic fallback"}
    if plan is None:
        plan, source = heuristic_plan(cols, question, intent, len(rows)), "heuristic"
        if validate_plan(plan, cols):
            yield {"type": "error", "message": "fast track: no usable plan for this CSV"}
            return

    label = {"cache": "plan cache hit · 0 ms planning",
             "planner": f"planned by {PLANNER_MODEL.split(':')[-1]} · {plan_ms} ms",
             "heuristic": "heuristic fallback (naive)"}[source]
    yield {"type": "status", "message": f"fast track: {label} → {plan.tool}"
           + (f" · filter {plan.filter}" if plan.filter else "")}

    spec, kpi, sentences = execute_plan(plan, rows)
    if kpi:
        yield {"type": "tool_call", "tool": "show_kpi", "args": json.dumps(kpi, ensure_ascii=False)}
        yield {"type": "tool_result", "tool": "show_kpi", "content": "ok"}
    elif spec:
        tool = f"generate_{spec['type']}_chart"
        yield {"type": "tool_call", "tool": tool, "args": json.dumps(spec, ensure_ascii=False)}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(render_url, json=spec, timeout=30)
            body = resp.json()
            yield {"type": "tool_result", "tool": tool,
                   "content": body.get("resultObj") or body.get("errorMessage", "render failed")}
        except Exception as e:
            yield {"type": "tool_result", "tool": tool, "content": f"render failed: {e}"}

    sentences.append({"cache": "(خطة معادة من الذاكرة، والتنفيذ بالكود.)",
                      "planner": "(الخطة من نموذج سريع، والأرقام محسوبة بالكود.)",
                      "heuristic": "(مسار احتياطي تقريبي — الأرقام محسوبة بالكود.)"}[source])
    yield {"type": "text", "delta": " ".join(sentences)}
    yield {"type": "done", "ms": round((time.perf_counter() - t0) * 1000), "plan_ms": plan_ms}
