"""
VSaaS Cloud API (prototype).

This module provides a lightweight FastAPI service that:
- Stores incoming events in a local SQLite DB
- Lists events with basic filters
- Answers simple operator questions via `/query` (optionally using an LLM)

Endpoints:
- `GET /health` -> basic health check
- `POST /events` -> ingest a batch of events
- `GET /events` -> list recent events
- `POST /query` -> list/summarize events from a natural-language question

Configuration:
- `VSAAS_DB_PATH` (default: `data/events.db`)
- `VSAAS_LLM_BASE_URL` (default: empty/disabled) points to an OpenAI-compatible server
- `VSAAS_LLM_MODEL` (default: `qwen3_vl_32b_instruct`)

Typical usage:
  Run via `scripts/run_cloud.sh`, which starts uvicorn and sets defaults.
"""

from __future__ import annotations

import json
import time
import urllib.error
from collections import Counter
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from .db import execute_many, get_db, init_db, query_all
from .llm import get_llm
from .models import ChatIn, EventsIn, QueryIn

app = FastAPI(title="VSaaS Cloud Prototype", version="0.1.0")


@app.on_event("startup")
def _startup() -> None:
    init_db(get_db())


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "ts_ms": int(time.time() * 1000)}


def _severity_rank(level: str | None) -> int:
    if not level:
        return 0
    return {"low": 0, "medium": 1, "high": 2}.get(level.strip().lower(), 0)


def _build_telemetry_context(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not events:
        return None

    counts = Counter(e.get("event_type", "unknown") for e in events)
    counts_str = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))

    camera_severity: dict[str, tuple[int, str]] = {}
    for e in events:
        cam = e.get("camera_id", "unknown")
        sev_rank = _severity_rank(e.get("severity"))
        prev = camera_severity.get(cam)
        if prev is None or sev_rank > prev[0]:
            camera_severity[cam] = (sev_rank, e.get("severity", "unknown"))

    high_cams = [cam for cam, (rank, _) in camera_severity.items() if rank >= 2]
    high_line = ""
    if high_cams:
        high_line = f"High severity cameras: {', '.join(high_cams)}."

    dwell = [e for e in events if e.get("event_type") == "dwell_time"]
    dwell_line = ""
    if dwell:
        sample = dwell[0]
        payload = sample.get("payload") or {}
        zone = payload.get("zone_id", "unknown")
        camera = payload.get("camera_id", sample.get("camera_id", "unknown"))
        dwell_ms = payload.get("dwell_ms")
        threshold_ms = payload.get("dwell_threshold_ms")
        dwell_line = f"Dwell event: camera={camera}, zone={zone}, dwell_ms={dwell_ms} threshold_ms={threshold_ms}."

    ppe = [e for e in events if e.get("event_type") == "ppe_violation"]
    ppe_line = ""
    if ppe:
        camera = ppe[0].get("camera_id", "unknown")
        ppe_line = f"PPE violations: {len(ppe)} (latest camera={camera})."

    intrusion = [
        e
        for e in events
        if e.get("event_type") == "zone_entry" and (e.get("payload") or {}).get("zone_kind") == "restricted"
    ]
    intrusion_line = ""
    if intrusion:
        zone = intrusion[0].get("payload", {}).get("zone_id", "unknown")
        camera = intrusion[0].get("camera_id", "unknown")
        intrusion_line = f"Intrusion: camera={camera} entered restricted zone={zone}."

    lines = [f"Event counts: {counts_str}."]
    if high_line:
        lines.append(high_line)
    if dwell_line:
        lines.append(dwell_line)
    if ppe_line:
        lines.append(ppe_line)
    if intrusion_line:
        lines.append(intrusion_line)

    camera_counts = Counter(e.get("camera_id", "unknown") for e in events)
    camera_lines = [f"{cam}: {cnt}" for cam, cnt in sorted(camera_counts.items())]

    detail_lines: list[str] = [
        f"Camera counts: {', '.join(camera_lines)}.",
        f"Event type breakdown: {counts_str}.",
    ]
    detail_lines.extend([line for line in [high_line, dwell_line, ppe_line, intrusion_line] if line])

    return {"summary": " ".join(lines), "detail_lines": detail_lines}


def _load_chat_ui_html() -> str:
    static_path = Path(__file__).resolve().parent / "static" / "chat.html"
    try:
        return static_path.read_text(encoding="utf-8")
    except Exception:
        return (
            "<html><body><h3>VSaaS Chat UI missing</h3>"
            "<p>Expected file: <code>src/vsaas/static/chat.html</code></p></body></html>"
        )


@app.get("/")
def chat_ui() -> HTMLResponse:
    return HTMLResponse(_load_chat_ui_html())


@app.post("/events")
def ingest_events(batch: EventsIn) -> dict[str, Any]:
    if not batch.events:
        raise HTTPException(status_code=400, detail="No events provided")

    rows: list[tuple[Any, ...]] = []
    for e in batch.events:
        rows.append(
            (
                e.id,
                e.ts_ms,
                e.camera_id,
                e.event_type,
                e.severity,
                e.summary,
                json.dumps(e.payload, separators=(",", ":")),
            )
        )

    execute_many(
        get_db(),
        """
        INSERT OR REPLACE INTO events(id, ts_ms, camera_id, event_type, severity, summary, payload_json)
        VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return {"ingested": len(rows)}


@app.get("/events")
def list_events(limit: int = 50, camera_id: str | None = None, event_type: str | None = None) -> dict[str, Any]:
    limit = max(1, min(limit, 200))

    where: list[str] = []
    params: list[Any] = []
    if camera_id:
        where.append("camera_id = ?")
        params.append(camera_id)
    if event_type:
        where.append("event_type = ?")
        params.append(event_type)

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    sql = (
        "SELECT id, ts_ms, camera_id, event_type, severity, summary, payload_json FROM events"
        + where_sql
        + " ORDER BY ts_ms DESC LIMIT ?"
    )
    params.append(limit)

    items = query_all(get_db(), sql, tuple(params))
    for it in items:
        it["payload"] = json.loads(it.pop("payload_json"))
    return {"items": items}


def _simple_question_router(question: str) -> dict[str, Any]:
    q = question.lower().strip()

    if q.startswith("show last"):
        n = 5
        for tok in q.split():
            if tok.isdigit():
                n = int(tok)
                break
        return {"action": "list", "limit": max(1, min(n, 200))}

    if "summarize" in q:
        n = 10
        for tok in q.split():
            if tok.isdigit():
                n = int(tok)
                break
        return {"action": "summarize", "limit": max(1, min(n, 200))}

    return {"action": "list", "limit": 10}


@app.post("/query")
def query(query_in: QueryIn) -> dict[str, Any]:
    question = query_in.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Empty question")

    llm = get_llm()
    route = _simple_question_router(question)

    events = list_events(limit=route["limit"])["items"]
    if route["action"] == "list":
        return {"mode": "list", "events": events}

    system = (
        "You are a security operations assistant. Summarize events without tool calls. "
        "Use plain text. Do not include hidden reasoning."
    )
    lines = [
        f"- ts_ms={e['ts_ms']} camera={e['camera_id']} type={e['event_type']} "
        f"sev={e['severity']} summary={e['summary']}"
        for e in events
    ]
    prompt = "Summarize these events for an operator in 3-5 bullet points:\n" + "\n".join(lines)

    if llm is None:
        by_type: dict[str, int] = {}
        for e in events:
            by_type[e["event_type"]] = by_type.get(e["event_type"], 0) + 1
        summary = "Event counts: " + ", ".join([f"{k}={v}" for k, v in sorted(by_type.items())])
        return {"mode": "summarize", "events": events, "summary": summary, "llm_used": False}

    try:
        summary = llm.chat(system=system, user=prompt, max_tokens=256, temperature=0.2)
        return {"mode": "summarize", "events": events, "summary": summary, "llm_used": True}
    except Exception as e:
        by_type: dict[str, int] = {}
        for ev in events:
            by_type[ev["event_type"]] = by_type.get(ev["event_type"], 0) + 1
        summary = "Event counts: " + ", ".join([f"{k}={v}" for k, v in sorted(by_type.items())])
        return {"mode": "summarize", "events": events, "summary": summary, "llm_used": False, "llm_error": str(e)}


@app.post("/chat")
def chat(chat_in: ChatIn) -> dict[str, Any]:
    if not chat_in.messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    llm = get_llm()
    include_events = bool(chat_in.include_events)
    max_events = int(chat_in.max_events)
    fallback_allowed = bool(chat_in.use_fallback_summary)

    last_user = ""
    for m in reversed(chat_in.messages):
        if m.role == "user":
            last_user = (m.content or "").strip()
            break

    # If the user asks for a summary but disabled event context in the UI, force-enable it.
    # This prevents the assistant from asking "what events?" for a self-contained question.
    wants_summary = bool(last_user) and any(tok in last_user.lower() for tok in ["summarize", "summary"])
    if wants_summary and fallback_allowed and (not include_events or max_events <= 0):
        include_events = True
        max_events = max(10, max_events)

    events: list[dict[str, Any]] = []
    if include_events and max_events > 0:
        events = list_events(limit=max_events)["items"]
    telemetry = _build_telemetry_context(events)

    def _fallback_summary(max_bullets: int = 3) -> str:
        if not events:
            return "No events are currently loaded."
        by_type: dict[str, int] = {}
        failures = 0
        for ev in events:
            by_type[ev["event_type"]] = by_type.get(ev["event_type"], 0) + 1
            if "failed" in (ev.get("summary", "") or "").lower():
                failures += 1
        counts = ", ".join([f"{k}={v}" for k, v in sorted(by_type.items())])
        newest = events[0]
        oldest = events[-1]
        bullets = [
            f"- Events: {len(events)} (types: {counts}).",
            f"- Newest: ts_ms={newest['ts_ms']} camera={newest['camera_id']} type={newest['event_type']} sev={newest['severity']} ({newest['summary']}).",
            f"- Oldest: ts_ms={oldest['ts_ms']} camera={oldest['camera_id']} type={oldest['event_type']} sev={oldest['severity']} ({oldest['summary']}).",
        ]
        if failures:
            bullets.append(f"- Capture failures observed: {failures}/{len(events)}.")
        return "\n".join(bullets[:max_bullets])

    system = (
        "You are a helpful VSaaS operator assistant.\n"
        "- Be concise and practical.\n"
        "- If you reference events, cite ts_ms + camera_id + type.\n"
        "- Do not invent events that are not in context.\n"
        "- Do not include hidden reasoning."
    )

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]

    telemetry = _build_telemetry_context(events)

    if events:
        lines = [
            f"- ts_ms={e['ts_ms']} camera_id={e['camera_id']} event_type={e['event_type']} severity={e['severity']} summary={e['summary']}"
            for e in events
        ]
        messages.append(
            {
                "role": "system",
                "content": (
                    "Definition: An 'event' is a single record from the VSaaS Cloud API database.\n"
                    "Here are the most recent events (most recent first):\n"
                    + "\n".join(lines)
                ),
            }
        )
        if telemetry:
            messages.append({"role": "system", "content": f"Telemetry summary: {telemetry}"})

    for m in chat_in.messages:
        messages.append({"role": m.role, "content": m.content})

    if llm is None:
        by_type: dict[str, int] = {}
        for e in events:
            by_type[e["event_type"]] = by_type.get(e["event_type"], 0) + 1
        counts = ", ".join([f"{k}={v}" for k, v in sorted(by_type.items())]) if by_type else "no events loaded"
        reply = f"LLM is disabled (`VSAAS_LLM_BASE_URL` not set). Recent event counts: {counts}."
        return {"reply": reply, "llm_used": False, "events_included": len(events)}

    try:
        reply = llm.chat_messages(messages=messages, max_tokens=chat_in.max_tokens, temperature=chat_in.temperature)
        reply_text = (reply or "").strip()

        # Heuristic: small/local models sometimes miss context and ask for clarification.
        if fallback_allowed and events and (
            not reply_text
            or ("not sure" in reply_text.lower() and "event" in reply_text.lower())
            or ("need more information" in reply_text.lower())
            or ("provide more" in reply_text.lower() and "detail" in reply_text.lower())
        ):
            reply_text = _fallback_summary(max_bullets=3)
            return {
                "reply": reply_text,
                "llm_used": False,
                "events_included": len(events),
                "model": llm.model,
                "llm_error": "LLM response did not use provided event context; returned fallback summary.",
                "fallback_used": True,
                "telemetry_summary": telemetry["summary"] if telemetry else None,
                "telemetry_details": telemetry.get("detail_lines") if telemetry else [],
            }

        return {
            "reply": reply_text,
            "llm_used": True,
            "events_included": len(events),
            "model": llm.model,
            "fallback_used": False,
            "telemetry_summary": telemetry["summary"] if telemetry else None,
            "telemetry_details": telemetry.get("detail_lines") if telemetry else [],
        }
    except Exception as e:
        code = getattr(e, "code", None)
        if isinstance(e, urllib.error.HTTPError):
            code = e.code
        if code == 429:
            by_type: dict[str, int] = {}
            for ev in events:
                by_type[ev["event_type"]] = by_type.get(ev["event_type"], 0) + 1
            counts = ", ".join([f"{k}={v}" for k, v in sorted(by_type.items())]) if by_type else "no events loaded"
            reply = (
                "Upstream LLM is rate-limited (HTTP 429). Try again in ~30–60s.\n"
                f"Fallback summary (no LLM): {counts}."
            )
            return {
                "reply": reply,
                "llm_used": False,
                "events_included": len(events),
                "llm_error": str(e),
                "telemetry_summary": telemetry["summary"] if telemetry else None,
                "telemetry_details": telemetry.get("detail_lines") if telemetry else [],
                "fallback_used": True,
            }
        return {
            "reply": f"LLM call failed: {e}",
            "llm_used": False,
            "events_included": len(events),
            "llm_error": str(e),
            "telemetry_summary": telemetry["summary"] if telemetry else None,
            "telemetry_details": telemetry.get("detail_lines") if telemetry else [],
            "fallback_used": False,
        }
