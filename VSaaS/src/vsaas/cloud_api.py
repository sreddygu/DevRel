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
from typing import Any

from fastapi import FastAPI, HTTPException

from .db import execute_many, get_db, init_db, query_all
from .llm import get_llm
from .models import EventsIn, QueryIn

app = FastAPI(title="VSaaS Cloud Prototype", version="0.1.0")


@app.on_event("startup")
def _startup() -> None:
    init_db(get_db())


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "ts_ms": int(time.time() * 1000)}


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
