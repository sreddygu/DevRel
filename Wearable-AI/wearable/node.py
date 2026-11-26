"""Gated wearable node: tiny model always on, large model only on a trigger.

Emits an AURA ``Event`` when the inferred context *changes* (so the hub's memory
holds a compact routine, not a sensor firehose) and calls ``on_burst`` only for
anomalies. ``stats`` quantifies the power model: how rarely the big model wakes.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from aura.core.events import Event

from .context import classify
from .sensors import Sample


class WearableNode:
    def __init__(
        self,
        *,
        hz: int = 25,
        window_s: float = 2.0,
        on_event: Callable[[Event], None] | None = None,
        on_burst: Callable[[Event], None] | None = None,
        confirm_windows: int = 2,
    ) -> None:
        self.size = int(hz * window_s)
        self.window_s = window_s
        self.on_event, self.on_burst = on_event, on_burst
        self.confirm = confirm_windows  # consecutive windows needed to accept a change (debounce)
        self.state: str | None = None
        self._candidate: tuple[str, int] | None = None
        self.stats = {"samples": 0, "windows": 0, "events": 0, "bursts": 0}

    def run(self, samples: Iterable[Sample]) -> list[Event]:
        emitted: list[Event] = []
        buf: list[Sample] = []
        for s in samples:
            self.stats["samples"] += 1
            buf.append(s)
            if len(buf) < self.size:
                continue
            window, buf = buf, []
            self.stats["windows"] += 1
            event = self._step(window)
            if event:
                emitted.append(event)
        return emitted

    def _step(self, window: list[Sample]) -> Event | None:
        state, f = classify(window)
        if state == self.state:
            self._candidate = None
            return None
        count = self._candidate[1] + 1 if self._candidate and self._candidate[0] == state else 1
        self._candidate = (state, count)
        if count < self.confirm and self.state is not None:
            return None
        self.state, self._candidate = state, None
        event = Event(
            event=f"Wearer is {state}" if state != "anomaly" else "Elevated heart rate while still",
            type="context",
            entities=[state],
            source="wearable",
            confidence=1.0,
            attributes={"motion_std": round(f["motion_std"], 3), "hr_mean": round(f["hr_mean"], 1),
                        "t_end": window[-1].t},
        )
        self.stats["events"] += 1
        if self.on_event:
            self.on_event(event)
        if state == "anomaly":
            self.stats["bursts"] += 1
            if self.on_burst:
                self.on_burst(event)
        return event

    def summary(self) -> dict:
        w = max(self.stats["windows"], 1)
        return {**self.stats, "big_model_duty": round(self.stats["bursts"] / w, 4),
                "event_ratio": round(self.stats["events"] / w, 4)}
