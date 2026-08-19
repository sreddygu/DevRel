# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""The AURA Event — the single data contract across the whole pipeline.

Vision and speech *produce* Events; memory *stores* them; the agent *reasons*
over them. Keeping one small, well-defined record here is what lets the
milestones be built independently.

The on-the-wire shape is a superset of the minimal form shown in the roadmap::

    {"timestamp": "10:24", "event": "Person entered room"}

A full Event adds structured fields (entities, location, source, confidence)
so later milestones can answer richer queries ("Where did I leave my laptop?",
"Who came today?") without changing the contract.

This module is intentionally dependency-free (stdlib only) so it imports on any
Python 3.10+ interpreter, including the bare system Python on-device.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


def _now_iso() -> str:
    """UTC timestamp in ISO-8601, e.g. ``2026-08-06T15:04:05+00:00``."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Event:
    """A single thing AURA perceived or inferred about the physical world.

    Attributes:
        event: Human-readable description, e.g. ``"Person entered room"``.
            This is the ``event`` key in the minimal roadmap JSON.
        timestamp: ISO-8601 time the event occurred. Defaults to "now" (UTC).
        type: Coarse category — ``"detection"``, ``"speech"``, ``"action"``,
            ``"scene"``, … Used to filter the memory store.
        entities: Named things involved, e.g. ``["package"]`` or ``["Neha"]``.
        location: Where it happened, e.g. ``"study room"`` — powers
            "where did I leave …" queries.
        source: What produced the event — ``"vision"``, ``"speech"``,
            ``"agent"``, or a specific camera/mic id.
        confidence: Detector/model confidence in ``[0.0, 1.0]`` when known.
        attributes: Free-form extra fields (bounding boxes, embeddings ref,
            image path, …) that don't warrant a first-class column.
        id: Stable unique id (uuid4 hex); auto-generated.
    """

    event: str
    timestamp: str = field(default_factory=_now_iso)
    type: str = "detection"
    entities: list[str] = field(default_factory=list)
    location: str | None = None
    source: str | None = None
    confidence: float | None = None
    attributes: dict = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_dict(self) -> dict:
        """Return a plain dict (JSON-ready), dropping ``None`` fields."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    def to_json(self, *, indent: int | None = None) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> Event:
        """Build an Event from a dict, ignoring unknown keys.

        Tolerant on purpose: an upstream producer may add fields we don't
        model yet — those land in ``attributes`` rather than raising.
        """
        known = {f for f in cls.__dataclass_fields__}  # noqa: C416
        core = {k: v for k, v in data.items() if k in known}
        extra = {k: v for k, v in data.items() if k not in known}
        if extra:
            core.setdefault("attributes", {}).update(extra)
        return cls(**core)

    @classmethod
    def from_json(cls, text: str) -> Event:
        """Parse an Event from a JSON string."""
        return cls.from_dict(json.loads(text))

    def __str__(self) -> str:  # e.g. "[15:04] Person entered room (study room)"
        loc = f" ({self.location})" if self.location else ""
        return f"[{self.timestamp}] {self.event}{loc}"
