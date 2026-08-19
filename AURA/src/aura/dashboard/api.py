# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""FastAPI application factory for the AURA dashboard.

Endpoints (wired as their milestones land):

    GET  /health          liveness probe
    GET  /events          list/filter remembered Events        (Milestone 3)
    POST /ask             ask a question about observed events  (Milestone 4)
    GET  /summary         today's summary                       (Milestone 4)

``fastapi`` is imported lazily inside :func:`create_app`, so importing this
module never requires the ``dashboard`` extra — only *calling* it does.
"""

from __future__ import annotations

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
        return {"status": "ok", "service": "aura", "version": "0.1.0"}

    # /events, /ask, /summary are added in Milestones 3–4 (see docs/ROADMAP.md),
    # backed by the injected `memory` and `llm` collaborators.

    return app
