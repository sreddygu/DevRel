# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""Milestone 3 (Memory) demo — add Events, then query / where_is / recall.

Runs on the base install (stdlib SQLite only); ``recall`` uses the keyword
fallback when the ``memory`` extra isn't present. Uses a throwaway database in
the system temp directory so it leaves nothing behind.

    python examples/memory_demo.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from aura.core.events import Event
from aura.memory.store import MemoryStore

# A morning's worth of observations, oldest first.
EVENTS = [
    Event(event="person entered room", timestamp="2026-08-06T09:15:00+00:00",
          type="detection", entities=["person"], location="study room", source="vision"),
    Event(event="laptop detected", timestamp="2026-08-06T09:16:00+00:00",
          type="detection", entities=["laptop"], location="study room", source="vision",
          confidence=0.88),
    Event(event="a package was delivered", timestamp="2026-08-06T15:15:00+00:00",
          type="detection", entities=["package"], location="front door", source="vision",
          confidence=0.92),
    Event(event="laptop detected", timestamp="2026-08-06T20:42:00+00:00",
          type="detection", entities=["laptop"], location="kitchen", source="vision",
          confidence=0.90),
    Event(event="light turned off", timestamp="2026-08-06T22:00:00+00:00",
          type="action", entities=["light"], source="agent"),
]


def main() -> int:
    db_path = str(Path(tempfile.gettempdir()) / "aura_memory_demo.db")
    Path(db_path).unlink(missing_ok=True)  # start fresh each run

    with MemoryStore(db_path).connect() as store:
        for ev in EVENTS:
            store.add_event(ev)
        print(f"Stored {len(EVENTS)} events in {db_path}\n")

        print("== query(type='detection') — what did AURA see? ==")
        for ev in store.query(type="detection"):
            print(" ", ev)

        print("\n== where_is('laptop') — last-seen location ==")
        found = store.where_is("laptop")
        print(" ", found.to_json() if found else "unknown")

        print("\n== recall('package') — semantic/keyword recall ==")
        for ev in store.recall("package"):
            print(" ", ev)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
