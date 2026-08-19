"""
SQLite storage helpers for VSaaS.

The cloud API stores events in a single SQLite DB for simplicity. The DB path is
configured via `VSAAS_DB_PATH` (default: `data/events.db`).

Schema (see `init_db`):
- `events(id PRIMARY KEY, ts_ms, camera_id, event_type, severity, summary, payload_json)`
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class Db:
    path: Path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn


def get_db() -> Db:
    p = os.environ.get("VSAAS_DB_PATH", "data/events.db")
    return Db(path=Path(p))


def init_db(db: Db) -> None:
    with db.connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
              id TEXT PRIMARY KEY,
              ts_ms INTEGER NOT NULL,
              camera_id TEXT NOT NULL,
              event_type TEXT NOT NULL,
              severity TEXT NOT NULL,
              summary TEXT NOT NULL,
              payload_json TEXT NOT NULL
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts_ms);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_camera ON events(camera_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);")


def execute_many(db: Db, sql: str, rows: Iterable[tuple[Any, ...]]) -> None:
    with db.connect() as conn:
        conn.executemany(sql, rows)
        conn.commit()


def query_all(db: Db, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    with db.connect() as conn:
        cur = conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
