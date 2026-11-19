from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from aura.core.events import Event
from aura.dashboard.api import create_app
from aura.memory.store import MemoryStore


def test_events_endpoint_can_use_memory_from_fastapi_worker_thread(tmp_path: Path) -> None:
    store = MemoryStore(str(tmp_path / "aura.db")).connect()
    store.add_event(Event(event="package delivered", entities=["package"]))
    client = TestClient(create_app(memory=store))

    response = client.get("/events")

    assert response.status_code == 200
    assert response.json()[0]["event"] == "package delivered"
    store.close()
