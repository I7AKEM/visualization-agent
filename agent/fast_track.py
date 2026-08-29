"""Fast track — answer with a chart and numbers WITHOUT any LLM.

Deterministic pipeline: profile the CSV, choose a form (the handoff intent wins
when present), aggregate, render via the private renderer, and compose a short
Arabic narrative from computed numbers. Milliseconds of compute + one render
round-trip; the smart track (the LLM agent) exists for everything this can't do.

Emits the same event dicts the web UI already understands:
  status / tool_call / tool_result / text / done
"""

from __future__ import annotations

import csv
import io
import re
import time

import httpx

AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
DATE_RE = re.compile(r"^\d{4}([-/]\d{1,2}){0,2}$|^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}$")
TIME_NAMES = re.compile(r"^(month|date|year|week|day|quarter|شهر|سنة|تاريخ|ربع|أسبوع|يوم)$", re.I)
MEASURE_NAMES = re.compile(r"(value|amount|count|total|transactions|قيمة|عدد|معاملات|إجمالي|مبلغ|سكان|population)", re.I)


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
        cols[name] = {"kind": kind, "distinct": len({str(v) for v in vals})}
    return cols


def choose(cols: dict, intent: str, n_rows: int) -> dict:
    """Pick measure/time/dim and a chart form; intent (from the data agent) wins."""
    numbers = [c for c, p in cols.items() if p["kind"] == "number"]
    dates = [c for c, p in cols.items() if p["kind"] == "date" or TIME_NAMES.match(c)]
    texts = [c for c, p in cols.items() if p["kind"] == "text" and 2 <= p["distinct"] <= 60 and c not in dates]
    measure = next((c for c in numbers if MEASURE_NAMES.search(c)), numbers[0] if numbers else None)
    time_col = dates[0] if dates else None
    dim = min(texts, key=lambda c: cols[c]["distinct"]) if texts else None

    intent = (intent or "").strip().lower()
    if intent == "kpi" or n_rows == 1 or (measure and not time_col and not dim):
        form = "kpi"
    elif intent == "trend" or (intent == "" and time_col):
        form = "line" if time_col else "column"
    elif intent in ("comparison", "ranking"):
        form = "column"
    elif intent == "distribution":
        form = "pie" if dim and cols[dim]["distinct"] <= 6 else "column"
    elif intent == "correlation" and len(numbers) >= 2:
        form = "scatter"
    else:
        form = "line" if time_col else ("column" if dim else "kpi")
    return {"form": form, "measure": measure, "time": time_col, "dim": dim}


def aggregate(rows, measure, key, group=None, other="أخرى"):
    acc, order = {}, []
    for r in rows:
        v = _num(r[measure])
        if v is None:
            continue
        k = (str(r[key]).strip(), str(r[group]).strip() if group else None)
        if k not in acc:
            acc[k] = 0
            order.append(k)
        acc[k] += v
    return [(k[0], k[1], acc[k]) for k in order]


def fast_events(csv_text: str, question: str, handoff: dict, render_url: str):
    t0 = time.perf_counter()
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    if not rows:
        yield {"type": "error", "message": "fast track: could not read the CSV"}
        return
    cols = profile(rows)
    pick = choose(cols, handoff.get("intent", ""), len(rows))
    measure, time_col, dim, form = pick["measure"], pick["time"], pick["dim"], pick["form"]
    if not measure:
        yield {"type": "error", "message": "fast track: no numeric column found"}
        return
    title = question if question and len(question) <= 70 else f"{measure} حسب {dim or time_col or ''}"

    sentences: list[str] = []
    spec = None

    if form == "kpi":
        total = sum(v for r in rows if (v := _num(r[measure])) is not None)
        yield {"type": "status", "message": f"fast track: KPI — no chart needed ({len(rows)} rows)"}
        yield {"type": "tool_call", "tool": "show_kpi", "args":
               __import__("json").dumps({"value": fmt(total), "label": f"إجمالي {measure}",
                                         "context": handoff.get("enriched") or question or ""}, ensure_ascii=False)}
        yield {"type": "tool_result", "tool": "show_kpi", "content": "ok"}
        sentences.append(f"إجمالي {measure}: {fmt(total)}.")
    elif form == "line":
        agg = aggregate(rows, measure, time_col, dim)
        groups = {}
        for t, g, v in agg:
            groups.setdefault(g, 0)
            groups[g] += v
        top5 = sorted(groups, key=groups.get, reverse=True)[:5] if dim else [None]
        data = sorted(
            [{"time": t, "value": round(v, 2), **({"group": g} if dim else {})}
             for t, g, v in agg if g in top5],
            key=lambda d: d["time"])
        spec = {"type": "line", "data": data, "title": title, "axisXTitle": time_col, "axisYTitle": measure}
        first, last = data[0], [d for d in data if not dim or d.get("group") == top5[0]][-1]
        top_series = [d for d in data if not dim or d.get("group") == top5[0]]
        if len(top_series) >= 2:
            a, b = top_series[0]["value"], top_series[-1]["value"]
            pct = (b - a) / a * 100 if a else 0
            who = f"{top5[0]}: " if dim else ""
            sentences.append(f"{who}{measure} {'ارتفع' if pct >= 0 else 'انخفض'} من {fmt(a)} إلى {fmt(b)} ({'+' if pct >= 0 else ''}{pct:.1f}%).")
    else:  # column / pie / scatter share the categorical path
        key = dim or time_col
        agg = sorted(aggregate(rows, measure, key), key=lambda x: -x[2])
        if len(agg) > 12:
            rest = sum(v for _, _, v in agg[12:])
            agg = agg[:12] + [("أخرى", None, rest)]
        data = [{"category": k, "value": round(v, 2)} for k, _, v in agg]
        chart_type = "pie" if form == "pie" else "column"
        spec = {"type": chart_type, "data": data, "title": title}
        if chart_type == "column":
            spec.update({"axisXTitle": key, "axisYTitle": measure})
        total = sum(d["value"] for d in data)
        top = data[0]
        sentences.append(f"{top['category']} في الصدارة بقيمة {fmt(top['value'])} ({top['value']/total*100:.1f}% من الإجمالي البالغ {fmt(total)}).")
        if len(data) > 1:
            sentences.append(f"أدنى قيمة: {data[-1]['category']} ({fmt(data[-1]['value'])}).")

    if spec:
        import json as _json
        tool = f"generate_{spec['type']}_chart"
        yield {"type": "status", "message":
               f"fast track: intent={handoff.get('intent') or 'auto'} → {spec['type']} · {len(rows)} rows → {len(spec['data'])} points"}
        yield {"type": "tool_call", "tool": tool, "args": _json.dumps(spec, ensure_ascii=False)}
        try:
            resp = httpx.post(render_url, json=spec, timeout=30)
            body = resp.json()
            yield {"type": "tool_result", "tool": tool,
                   "content": body.get("resultObj") or body.get("errorMessage", "render failed")}
        except Exception as e:
            yield {"type": "tool_result", "tool": tool, "content": f"render failed: {e}"}

    sentences.append("(المسار السريع: الأرقام محسوبة بالكود مباشرة، دون نموذج لغوي.)")
    yield {"type": "text", "delta": " ".join(sentences)}
    yield {"type": "done", "ms": round((time.perf_counter() - t0) * 1000)}
