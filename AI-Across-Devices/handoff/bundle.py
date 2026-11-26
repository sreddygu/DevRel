"""Context bundles: the unit of state that moves between devices.

A bundle is a JSON document holding recent AURA Events plus a checksum. Only
grounded context crosses the wire; attributes that could carry raw sensor data
(frames, audio, embeddings) are stripped before export.
"""

from __future__ import annotations

import hashlib
import json
import socket
from datetime import datetime, timezone

from aura.core.events import Event
from aura.memory.store import MemoryStore

SCHEMA_VERSION = 1

# Attribute keys (case-insensitive substring match) that may hold raw sensor data.
RAW_KEYS = ("image", "frame", "audio", "pcm", "wav", "embedding", "raw", "blob", "jpeg", "png")


class BundleError(ValueError):
    """The bundle is malformed, from an unknown schema, or fails its checksum."""


def sanitize(event: Event) -> dict:
    """Event as a dict with raw-sensor attributes removed."""
    data = event.to_dict()
    attrs = data.get("attributes") or {}
    data["attributes"] = {
        k: v for k, v in attrs.items() if not any(r in k.lower() for r in RAW_KEYS)
    }
    return data


def _digest(events: list[dict]) -> str:
    canonical = json.dumps(events, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_bundle(
    store: MemoryStore,
    *,
    since: str | None = None,
    limit: int = 500,
    node: str | None = None,
) -> dict:
    """Export events at or after ``since`` (ISO-8601), oldest first."""
    events = [sanitize(e) for e in reversed(store.query(since=since, limit=limit))]
    return {
        "schema": SCHEMA_VERSION,
        "node": node or socket.gethostname(),
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "since": since,
        "count": len(events),
        "sha256": _digest(events),
        "events": events,
    }


def verify_bundle(bundle: dict) -> None:
    if not isinstance(bundle, dict) or bundle.get("schema") != SCHEMA_VERSION:
        raise BundleError(f"unsupported bundle schema: {bundle.get('schema') if isinstance(bundle, dict) else None!r}")
    events = bundle.get("events")
    if not isinstance(events, list):
        raise BundleError("bundle has no events list")
    if bundle.get("sha256") != _digest(events):
        raise BundleError("bundle checksum mismatch")


def import_bundle(store: MemoryStore, bundle: dict) -> dict:
    """Merge a bundle into ``store``. Idempotent: existing event ids are skipped."""
    verify_bundle(bundle)
    existing = {e.id for e in store.query(limit=1_000_000)}
    added = skipped = 0
    for data in bundle["events"]:
        event = Event.from_dict(data)
        if event.id in existing:
            skipped += 1
            continue
        store.add_event(event)
        added += 1
    return {"added": added, "skipped": skipped, "from": bundle.get("node")}
