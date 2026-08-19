# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""Smoke tests for the AURA scaffold.

These verify the two things the v0.1 scaffold must guarantee:
1. Every module in the package imports cleanly with only the base install
   (no vision/speech/memory/agent/dashboard extras present).
2. The core Event contract round-trips through JSON as the roadmap specifies.
"""

from __future__ import annotations

import importlib

import pytest

MODULES = [
    "aura",
    "aura.cli",
    "aura.config",
    "aura.core",
    "aura.core.events",
    "aura.core.pipeline",
    "aura.vision",
    "aura.vision.camera",
    "aura.vision.detector",
    "aura.speech",
    "aura.speech.stt",
    "aura.speech.tts",
    "aura.memory",
    "aura.memory.store",
    "aura.agent",
    "aura.agent.llm",
    "aura.agent.tools",
    "aura.agent.genie_server",
    "aura.dashboard",
    "aura.dashboard.api",
]


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name: str) -> None:
    """Every submodule imports without any optional (extra) dependency."""
    assert importlib.import_module(name) is not None


def test_version() -> None:
    import aura

    assert aura.__version__ == "0.1.0"


def test_event_minimal_shape() -> None:
    """The minimal roadmap JSON {timestamp, event} is representable."""
    from aura.core.events import Event

    ev = Event(event="Person entered room", timestamp="10:24")
    d = ev.to_dict()
    assert d["event"] == "Person entered room"
    assert d["timestamp"] == "10:24"


def test_event_json_roundtrip() -> None:
    """Event → JSON → Event preserves the meaningful fields."""
    from aura.core.events import Event

    ev = Event(
        event="package detected",
        timestamp="15:15",
        type="detection",
        entities=["package"],
        location="front door",
        source="vision",
        confidence=0.92,
    )
    clone = Event.from_json(ev.to_json())
    assert clone.event == ev.event
    assert clone.timestamp == ev.timestamp
    assert clone.entities == ["package"]
    assert clone.location == "front door"
    assert clone.confidence == pytest.approx(0.92)


def test_event_from_dict_tolerates_unknown_keys() -> None:
    """Unknown upstream fields land in attributes rather than raising."""
    from aura.core.events import Event

    ev = Event.from_dict({"event": "x", "future_field": 123})
    assert ev.attributes["future_field"] == 123


def test_detector_to_events_needs_no_model() -> None:
    """Detector.to_events bridges detections → Events without loading a model."""
    from aura.vision.detector import Detection, Detector

    det = Detector("nonexistent.onnx")
    events = det.to_events([Detection("person", 0.9, (0, 0, 10, 10))], location="lab")
    assert len(events) == 1
    assert events[0].entities == ["person"]
    assert events[0].location == "lab"
    assert events[0].type == "detection"


def test_stub_raises_not_implemented() -> None:
    """A representative not-yet-built capability is a clear NotImplementedError stub."""
    from aura.agent.tools import default_tools

    # Milestone 5 (Action) tools are still stubs — invoking one must raise.
    set_light = next(t for t in default_tools() if t.name == "set_light")
    with pytest.raises(NotImplementedError):
        set_light.invoke(name="workshop", state="on")
