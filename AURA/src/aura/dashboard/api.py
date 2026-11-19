# Author: Srinivas Reddy Gudala
# Email: sreddygu@qti.qualcomm.com
# Last Updated: 2026-08-17
# Version: 1.0
#
"""FastAPI application factory for the AURA dashboard.

Endpoints:

    GET  /health          liveness probe
    GET  /events          list/filter remembered Events        (Milestone 3)
    POST /ask             ask a question about observed events  (Milestone 4)
    GET  /summary         today's summary                       (Milestone 4)

``fastapi`` is imported lazily inside :func:`create_app`, so importing this
module never requires the ``dashboard`` extra — only *calling* it does.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def create_app(*, memory: Any = None, llm: Any = None) -> Any:
    """Build and return the FastAPI app.

    Args:
        memory: an :class:`aura.memory.store.MemoryStore` (for ``/events``).
        llm: an :class:`aura.agent.llm.LocalLLM` (for ``/ask`` and ``/summary``).

    Raises:
        RuntimeError: if the ``dashboard`` extra (fastapi) is not installed.
    """
    try:
        from fastapi import FastAPI
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on extra
        raise RuntimeError(
            "The dashboard requires the 'dashboard' extra:\n"
            '    pip install -e ".[dashboard]"'
        ) from exc

    app = FastAPI(title="AURA", version="0.1.0")

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "service": "aura",
            "version": "0.1.0",
            "memory": memory is not None,
            "llm": llm is not None,
        }

    @app.get("/events")
    def events(
        since: str | None = None,
        until: str | None = None,
        entity: str | None = None,
        type: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        if memory is None:
            raise RuntimeError("The dashboard needs a memory store for /events.")
        limit = max(1, min(limit, 500))
        return [event.to_dict() for event in memory.query(
            since=since, until=until, entity=entity, type=type, limit=limit
        )]

    @app.get("/knowledge")
    def knowledge(query: str, limit: int = 5) -> list[dict[str, str]]:
        if memory is None:
            raise RuntimeError("The dashboard needs a memory store for /knowledge.")
        return memory.recall_knowledge(query, k=max(1, min(limit, 50)))

    @app.post("/ask")
    def ask(payload: dict[str, Any]) -> dict[str, str]:
        if memory is None or llm is None:
            raise RuntimeError("The dashboard needs both memory and llm for /ask.")
        question = str(payload.get("question", "")).strip()
        if not question:
            raise ValueError("question is required")
        return {"question": question, "answer": llm.answer(question, memory.recall_context(question, k=5))}

    @app.get("/summary")
    def summary() -> dict[str, str]:
        if memory is None or llm is None:
            raise RuntimeError("The dashboard needs both memory and llm for /summary.")
        today = datetime.now(timezone.utc).date().isoformat()
        events_today = memory.query(since=f"{today}T00:00:00+00:00")
        return {"date": today, "summary": llm.summarize(events_today)}

    return app
