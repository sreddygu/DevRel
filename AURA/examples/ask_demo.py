# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""Milestone 4 (Brain) demo — "What happened today?" over remembered Events.

Populates a temp memory store with a day's observations, then asks a local,
OpenAI-compatible LLM (llama.cpp ``llama-server`` / Genie) to summarize the day
and answer a grounded question. Configure the endpoint via AURA_LLM_BASE_URL /
AURA_LLM_MODEL (see .env.example); defaults to http://127.0.0.1:8080.

    python examples/ask_demo.py

If no LLM server is reachable, the demo still prints the retrieved context so
the memory→reasoning wiring is visible without a running model.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from aura.agent.llm import LocalLLM
from aura.config import load_settings
from aura.core.events import Event
from aura.core.pipeline import AuraPipeline
from aura.memory.store import MemoryStore

EVENTS = [
    Event(event="person entered room", timestamp="2026-08-06T09:15:00+00:00",
          type="detection", entities=["person"], location="study room", source="vision"),
    Event(event="a package was delivered", timestamp="2026-08-06T14:00:00+00:00",
          type="detection", entities=["package"], location="front door", source="vision"),
    Event(event="package left on the front table", timestamp="2026-08-06T14:02:00+00:00",
          type="detection", entities=["package"], location="front table", source="vision"),
    Event(event="light turned off", timestamp="2026-08-06T16:15:00+00:00",
          type="action", entities=["light"], source="agent"),
]


def main() -> int:
    settings = load_settings()
    db_path = str(Path(tempfile.gettempdir()) / "aura_ask_demo.db")
    Path(db_path).unlink(missing_ok=True)

    with MemoryStore(db_path).connect() as store:
        for ev in EVENTS:
            store.add_event(ev)

        llm = LocalLLM(settings.llm_base_url, model=settings.llm_model,
                       no_think=settings.llm_no_think)
        pipe = AuraPipeline(memory=store, llm=llm)

        try:
            print("== Summarize today's events ==")
            print(llm.summarize(store.query()), "\n")

            print('== ask("What happened while I was gone?") ==')
            print(pipe.ask("What happened while I was gone?"), "\n")

            print('== ask("Where is the package?") ==')
            print(pipe.ask("Where is the package?"))
        except Exception as exc:  # noqa: BLE001 — demo: show wiring without a server
            print(f"[no LLM at {settings.llm_base_url}: {type(exc).__name__}]")
            print("Retrieved context that WOULD be sent to the LLM:")
            for ev in store.recall("package"):
                print(" ", ev)
            return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
