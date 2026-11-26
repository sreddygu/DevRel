"""Run from Wearable-AI: PYTHONPATH=../AURA/src:. pytest tests"""

from __future__ import annotations

from aura.memory.store import MemoryStore
from wearable import WearableNode, simulate


def _run(**kw):
    node = WearableNode(**kw)
    return node, node.run(simulate())


def test_default_day_produces_expected_context_sequence() -> None:
    _, events = _run()
    assert [e.entities[0] for e in events] == ["resting", "walking", "running", "resting", "anomaly", "resting"]


def test_big_model_wakes_only_for_anomaly() -> None:
    bursts = []
    node, _ = _run(on_burst=bursts.append)
    assert [b.entities[0] for b in bursts] == ["anomaly"]
    s = node.summary()
    assert s["bursts"] == 1 and s["big_model_duty"] <= 1 / 40
    assert s["events"] < s["windows"] / 5  # compact routine, not a firehose


def test_deterministic_for_a_seed() -> None:
    a = [(e.entities[0], e.attributes["t_end"]) for e in WearableNode().run(simulate(seed=3))]
    b = [(e.entities[0], e.attributes["t_end"]) for e in WearableNode().run(simulate(seed=3))]
    assert a == b


def test_events_land_in_aura_memory(tmp_path) -> None:
    with MemoryStore(str(tmp_path / "w.db")).connect() as store:
        WearableNode(on_event=store.add_event).run(simulate())
        assert len(store.query(type="context")) == 6
        assert store.query(entity="anomaly")[0].source == "wearable"


def test_short_blip_is_debounced() -> None:
    blip = [("resting", 10), ("walking", 2), ("resting", 10)]  # one 2 s window of motion
    states = [e.entities[0] for e in WearableNode().run(simulate(blip))]
    assert states == ["resting"]
