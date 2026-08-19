# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""Event + object-location store (Milestone 3).

Two layers behind one interface:

* **SQLite** (stdlib ``sqlite3``) — the structured event log and last-seen
  object locations. Powers exact/time/entity queries.
* **Vector store** (Chroma, in the ``memory`` extra) — embeddings of event
  descriptions for semantic recall ("anything about a package?").

Only the vector layer needs the optional dependency; the SQLite layer is
stdlib, so basic persistence works from the base install. When the vector
layer is unavailable, :meth:`MemoryStore.recall` degrades gracefully to a
SQLite keyword search rather than raising.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from aura.core.events import Event

# Columns of the ``events`` table, in Event-field order. entities/attributes
# are stored as JSON text; everything else maps to a scalar column.
_EVENT_COLUMNS = (
    "id",
    "event",
    "timestamp",
    "type",
    "entities",
    "location",
    "source",
    "confidence",
    "attributes",
)

# Words too generic to be useful search keys in the recall fallback. Kept small
# and stdlib-only (no NLP dependency); the vector store handles real semantics.
_STOPWORDS = frozenset(
    "a an the is are was were be been being do did does what when where who whom "
    "which why how i you he she it we they me my your of to in on at for and or "
    "did was gone happened while about with there here that this these those".split()
)


def _keywords(text: str) -> list[str]:
    """Split a query/question into lowercase content words (len>2, non-stop)."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w for w in words if len(w) > 2 and w not in _STOPWORDS]


class MemoryStore:
    """AURA's long-term memory.

    Args:
        db_path: SQLite database file. Defaults to ``./aura.db``.
        vector_dir: Directory for the vector store. ``None`` disables semantic
            recall (SQLite-only mode — :meth:`recall` falls back to keyword
            search).
    """

    def __init__(self, db_path: str = "./aura.db", *, vector_dir: str | None = None) -> None:
        self.db_path = db_path
        self.vector_dir = vector_dir
        self._conn: sqlite3.Connection | None = None
        self._vectors: Any = None  # lazily-created Chroma collection

    def connect(self) -> MemoryStore:
        """Open the SQLite connection and create tables if absent."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id          TEXT PRIMARY KEY,
                event       TEXT NOT NULL,
                timestamp   TEXT NOT NULL,
                type        TEXT,
                entities    TEXT,   -- JSON array
                location    TEXT,
                source      TEXT,
                confidence  REAL,
                attributes  TEXT    -- JSON object
            );
            CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_events_type      ON events(type);

            CREATE TABLE IF NOT EXISTS object_locations (
                object    TEXT PRIMARY KEY,
                location  TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                event_id  TEXT NOT NULL
            );
            """
        )
        conn.commit()
        self._conn = conn
        return self

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("MemoryStore is not connected — call connect() first.")
        return self._conn

    def add_event(self, event: Event) -> str:
        """Persist an Event; returns its id. Also indexes it for recall."""
        conn = self._require_conn()
        conn.execute(
            f"INSERT OR REPLACE INTO events ({', '.join(_EVENT_COLUMNS)}) "
            f"VALUES ({', '.join('?' for _ in _EVENT_COLUMNS)})",
            (
                event.id,
                event.event,
                event.timestamp,
                event.type,
                json.dumps(event.entities),
                event.location,
                event.source,
                event.confidence,
                json.dumps(event.attributes),
            ),
        )

        # Update object last-seen locations: last write wins by timestamp, so a
        # newer sighting overwrites an older one but a stale replay does not.
        if event.location:
            for obj in event.entities:
                row = conn.execute(
                    "SELECT timestamp FROM object_locations WHERE object = ?", (obj,)
                ).fetchone()
                if row is None or event.timestamp >= row["timestamp"]:
                    conn.execute(
                        "INSERT OR REPLACE INTO object_locations "
                        "(object, location, timestamp, event_id) VALUES (?, ?, ?, ?)",
                        (obj, event.location, event.timestamp, event.id),
                    )
        conn.commit()

        self._index_vector(event)
        return event.id

    def query(
        self,
        *,
        since: str | None = None,
        until: str | None = None,
        entity: str | None = None,
        type: str | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Structured lookup over the SQLite event log (time/entity/type)."""
        conn = self._require_conn()
        clauses: list[str] = []
        params: list[Any] = []
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since)
        if until is not None:
            clauses.append("timestamp <= ?")
            params.append(until)
        if type is not None:
            clauses.append("type = ?")
            params.append(type)
        if entity is not None:
            # entities is a JSON array like ["package"]; match the quoted token
            # so "cat" doesn't match "category".
            clauses.append("entities LIKE ?")
            params.append(f'%"{entity}"%')

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        rows = conn.execute(
            f"SELECT * FROM events {where} ORDER BY timestamp DESC LIMIT ?", params
        ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def recall(self, text: str, *, k: int = 5) -> list[Event]:
        """Semantic recall — the ``k`` Events most similar to ``text``.

        Uses the Chroma vector store when available; otherwise degrades to a
        SQLite keyword (substring) search so the base install still works.
        """
        collection = self._vector_collection()
        if collection is not None:
            result = collection.query(query_texts=[text], n_results=k)
            ids = (result.get("ids") or [[]])[0]
            if not ids:
                return []
            conn = self._require_conn()
            placeholders = ", ".join("?" for _ in ids)
            rows = conn.execute(
                f"SELECT * FROM events WHERE id IN ({placeholders})", list(ids)
            ).fetchall()
            by_id = {r["id"]: self._row_to_event(r) for r in rows}
            return [by_id[i] for i in ids if i in by_id]  # preserve rank order

        # Fallback: keyword match on the event description. The query is often a
        # full question ("Where is the package?"), so match on individual words
        # (not the whole string) and rank by how many distinct keywords hit.
        conn = self._require_conn()
        keywords = _keywords(text)
        if not keywords:
            rows = conn.execute(
                "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?", (k,)
            ).fetchall()
            return [self._row_to_event(r) for r in rows]

        like = " OR ".join("event LIKE ?" for _ in keywords)
        params = [f"%{w}%" for w in keywords]
        rows = conn.execute(f"SELECT * FROM events WHERE {like}", params).fetchall()
        events = [self._row_to_event(r) for r in rows]

        def score(ev: Event) -> tuple[int, str]:
            hits = sum(1 for w in keywords if w in ev.event.lower())
            return (hits, ev.timestamp)  # most keyword hits, then most recent

        events.sort(key=score, reverse=True)
        return events[:k]

    def where_is(self, obj: str) -> Event | None:
        """Last-seen location of an object ("Where did I leave my laptop?")."""
        conn = self._require_conn()
        row = conn.execute(
            "SELECT event_id FROM object_locations WHERE object = ?", (obj,)
        ).fetchone()
        if row is None:
            return None
        ev = conn.execute("SELECT * FROM events WHERE id = ?", (row["event_id"],)).fetchone()
        return self._row_to_event(ev) if ev is not None else None

    def close(self) -> None:
        """Close the SQLite connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> MemoryStore:
        return self.connect()

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ─── internals ────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> Event:
        """Rebuild an Event from a ``events`` table row."""
        return Event(
            id=row["id"],
            event=row["event"],
            timestamp=row["timestamp"],
            type=row["type"],
            entities=json.loads(row["entities"]) if row["entities"] else [],
            location=row["location"],
            source=row["source"],
            confidence=row["confidence"],
            attributes=json.loads(row["attributes"]) if row["attributes"] else {},
        )

    def _vector_collection(self) -> Any:
        """Return the Chroma collection, or ``None`` if the extra/dir is absent.

        The ``chromadb`` import is lazy so the base install imports this module
        without the ``memory`` extra.
        """
        if self.vector_dir is None:
            return None
        if self._vectors is not None:
            return self._vectors
        try:
            import chromadb  # noqa: PLC0415  (lazy: only when recall is used)
        except ImportError:
            return None
        client = chromadb.PersistentClient(path=self.vector_dir)
        self._vectors = client.get_or_create_collection("aura_events")
        return self._vectors

    def _index_vector(self, event: Event) -> None:
        """Add an event's description to the vector store when enabled."""
        collection = self._vector_collection()
        if collection is None:
            return
        collection.upsert(ids=[event.id], documents=[event.event])
