# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""Tests for aura.memory.store.MemoryStore (Milestone 3).

Stdlib-only: every test runs against a temporary SQLite file with no
``memory`` extra installed, so ``recall`` exercises the keyword fallback.
"""

from __future__ import annotations

from aura.core.events import Event
from aura.memory.store import MemoryStore


def _store(tmp_path) -> MemoryStore:
    return MemoryStore(str(tmp_path / "aura.db")).connect()


def test_add_and_query_roundtrip(tmp_path) -> None:
    """add_event then query returns an equal Event with fields preserved."""
    with _store(tmp_path) as store:
        ev = Event(
            event="package detected",
            timestamp="2026-08-06T15:15:00+00:00",
            type="detection",
            entities=["package"],
            location="front door",
            source="vision",
            confidence=0.92,
        )
        store.add_event(ev)

        (got,) = store.query()
        assert got.id == ev.id
        assert got.event == "package detected"
        assert got.entities == ["package"]
        assert got.location == "front door"
        assert got.confidence == 0.92
        assert got.type == "detection"


def test_query_filters(tmp_path) -> None:
    """query filters by type, entity, and since/until time window."""
    with _store(tmp_path) as store:
        store.add_event(Event(event="person entered", timestamp="2026-08-06T09:00:00+00:00",
                              type="detection", entities=["person"], location="lab"))
        store.add_event(Event(event="light turned on", timestamp="2026-08-06T10:00:00+00:00",
                              type="action", entities=["light"]))
        store.add_event(Event(event="person left", timestamp="2026-08-06T11:00:00+00:00",
                              type="detection", entities=["person"], location="lab"))

        assert len(store.query(type="detection")) == 2
        assert len(store.query(type="action")) == 1
        assert len(store.query(entity="person")) == 2
        assert len(store.query(entity="light")) == 1

        window = store.query(since="2026-08-06T09:30:00+00:00",
                             until="2026-08-06T10:30:00+00:00")
        assert len(window) == 1
        assert window[0].event == "light turned on"


def test_entity_filter_is_token_exact(tmp_path) -> None:
    """entity filter matches the quoted JSON token, not a substring."""
    with _store(tmp_path) as store:
        store.add_event(Event(event="cat seen", entities=["cat"]))
        store.add_event(Event(event="category tag", entities=["category"]))
        assert len(store.query(entity="cat")) == 1


def test_persistence_across_reopen(tmp_path) -> None:
    """Events survive closing and reopening the same db_path."""
    db = str(tmp_path / "aura.db")
    with MemoryStore(db).connect() as store:
        store.add_event(Event(event="persisted", entities=["thing"]))

    with MemoryStore(db).connect() as store:
        assert len(store.query()) == 1
        assert store.query()[0].event == "persisted"


def test_where_is_returns_last_seen(tmp_path) -> None:
    """where_is returns the most recent location Event for an object."""
    with _store(tmp_path) as store:
        store.add_event(Event(event="laptop detected", timestamp="2026-08-06T08:00:00+00:00",
                              entities=["laptop"], location="study room"))
        store.add_event(Event(event="laptop detected", timestamp="2026-08-06T20:42:00+00:00",
                              entities=["laptop"], location="kitchen"))

        found = store.where_is("laptop")
        assert found is not None
        assert found.location == "kitchen"
        assert store.where_is("backpack") is None


def test_where_is_ignores_stale_replay(tmp_path) -> None:
    """An out-of-order (older) sighting does not overwrite a newer location."""
    with _store(tmp_path) as store:
        store.add_event(Event(event="keys detected", timestamp="2026-08-06T20:00:00+00:00",
                              entities=["keys"], location="hallway"))
        store.add_event(Event(event="keys detected", timestamp="2026-08-06T08:00:00+00:00",
                              entities=["keys"], location="car"))
        assert store.where_is("keys").location == "hallway"


def test_recall_keyword_fallback(tmp_path) -> None:
    """Without the vector extra, recall does a keyword match on descriptions."""
    with _store(tmp_path) as store:
        store.add_event(Event(event="a package was delivered", entities=["package"]))
        store.add_event(Event(event="person entered room", entities=["person"]))

        hits = store.recall("package")
        assert len(hits) == 1
        assert "package" in hits[0].event


def test_recall_matches_keywords_in_a_question(tmp_path) -> None:
    """A full question recalls events sharing a content word (not whole-string)."""
    with _store(tmp_path) as store:
        store.add_event(Event(event="a package was delivered", entities=["package"]))
        store.add_event(Event(event="light turned off", entities=["light"]))

        # "package" is the only content keyword that hits an event.
        hits = store.recall("Where is the package?")
        assert [h.event for h in hits] == ["a package was delivered"]


def test_recall_ranks_by_keyword_hit_count(tmp_path) -> None:
    """Events matching more query keywords rank first."""
    with _store(tmp_path) as store:
        store.add_event(Event(event="package delivered at front door",
                              timestamp="2026-08-06T09:00:00+00:00"))
        store.add_event(Event(event="package left on front table",
                              timestamp="2026-08-06T08:00:00+00:00"))
        # "front table package" -> second event hits 3 keywords, first hits 2.
        hits = store.recall("front table package")
        assert hits[0].event == "package left on front table"
