#!/usr/bin/env python3
"""Replay stored VSaaS events into the Cloud API."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable


def load_events(db_path: str, limit: int | None = None) -> list[dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, ts_ms, camera_id, event_type, severity, summary, payload_json "
            "FROM events ORDER BY ts_ms ASC"
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    if limit:
        rows = rows[:limit]

    events: list[dict[str, Any]] = []
    for row in rows:
        payload_json = row["payload_json"]
        payload: dict[str, Any]
        if payload_json:
            try:
                payload = json.loads(payload_json)
            except json.JSONDecodeError:
                payload = {}
        else:
            payload = {}
        events.append(
            {
                "id": row["id"],
                "ts_ms": int(row["ts_ms"]) if row["ts_ms"] is not None else int(time.time() * 1000),
                "camera_id": row["camera_id"],
                "event_type": row["event_type"],
                "severity": row["severity"],
                "summary": row["summary"],
                "payload": payload,
            }
        )
    return events


def chunked(seq: Iterable[Any], size: int) -> Iterable[list[Any]]:
    batch: list[Any] = []
    for item in seq:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def post_batch(base_url: str, batch: list[dict[str, Any]]) -> None:
    url = base_url.rstrip("/") + "/events"
    payload = json.dumps({"events": batch}, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        resp.read()


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay VSaaS events into the Cloud API.")
    parser.add_argument(
        "--db-path",
        default="data/events.db",
        help="Path to the SQLite events database (default: %(default)s).",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:9000",
        help="Base URL of the Cloud API (default: %(default)s).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="Number of events to send per POST (default: %(default)s).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Replay only the first N rows from the DB.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned actions without posting to the API.",
    )
    args = parser.parse_args()

    db_path = os.path.expanduser(args.db_path)
    if not Path(db_path).exists():
        print(f"ERROR: events database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    events = load_events(db_path, limit=args.limit)
    if not events:
        print("No events to replay.")
        return

    print(f"Loaded {len(events)} events from {db_path}")
    if args.dry_run:
        print("Dry run; skipping posting.")
        return

    for idx, batch in enumerate(chunked(events, args.batch_size), start=1):
        print(f"Posting batch {idx}/{(len(events) + args.batch_size - 1) // args.batch_size} ({len(batch)} events)...")
        try:
            post_batch(args.base_url, batch)
        except urllib.error.HTTPError as e:
            print(f"HTTP error {e.code} while posting batch {idx}: {e.reason}", file=sys.stderr)
            raise
        except urllib.error.URLError as e:
            print(f"URL error while posting batch {idx}: {e}", file=sys.stderr)
            raise
        time.sleep(0.1)

    print("Replay complete.")


if __name__ == "__main__":
    main()
