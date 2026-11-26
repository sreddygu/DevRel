"""Handoff tests. Run with: PYTHONPATH=../AURA/src:. pytest tests (from AI-Across-Devices)."""

from __future__ import annotations

import pytest

from aura.core.events import Event
from aura.memory.store import MemoryStore
from handoff import BundleError, build_bundle, catch_up, import_bundle, make_server
from handoff.transport import serve_in_thread

TOKEN = "t0ken-for-tests"


def _hub(tmp_path):
    store = MemoryStore(str(tmp_path / "hub.db")).connect()
    store.add_event(Event(event="forklift entered bay", timestamp="2026-08-06T09:00:00+00:00",
                          entities=["forklift"], location="loading bay",
                          attributes={"image_path": "/tmp/f.jpg", "bbox": [1, 2, 3, 4]}))
    store.add_event(Event(event="package unloaded", timestamp="2026-08-06T09:30:00+00:00",
                          entities=["package"], location="loading bay"))
    return store


def test_bundle_strips_raw_sensor_attributes(tmp_path) -> None:
    with _hub(tmp_path) as hub:
        bundle = build_bundle(hub, node="iq8")
    first = bundle["events"][0]
    assert "image_path" not in first["attributes"]
    assert first["attributes"]["bbox"] == [1, 2, 3, 4]
    assert [e["event"] for e in bundle["events"]] == ["forklift entered bay", "package unloaded"]


def test_import_is_idempotent_and_preserves_object_locations(tmp_path) -> None:
    with _hub(tmp_path) as hub, MemoryStore(str(tmp_path / "laptop.db")).connect() as laptop:
        bundle = build_bundle(hub)
        assert import_bundle(laptop, bundle)["added"] == 2
        assert import_bundle(laptop, bundle) == {"added": 0, "skipped": 2, "from": bundle["node"]}
        assert laptop.where_is("package").location == "loading bay"


def test_tampered_bundle_is_rejected(tmp_path) -> None:
    with _hub(tmp_path) as hub, MemoryStore(str(tmp_path / "l.db")).connect() as laptop:
        bundle = build_bundle(hub)
        bundle["events"][0]["event"] = "tampered"
        with pytest.raises(BundleError):
            import_bundle(laptop, bundle)


def test_since_filters_events(tmp_path) -> None:
    with _hub(tmp_path) as hub:
        assert build_bundle(hub, since="2026-08-06T09:15:00+00:00")["count"] == 1


def test_catch_up_over_http_and_auth(tmp_path) -> None:
    _hub(tmp_path).close()
    server = make_server(str(tmp_path / "hub.db"), TOKEN, port=0, node="hub")
    serve_in_thread(server)
    url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with MemoryStore(str(tmp_path / "laptop.db")).connect() as laptop:
            assert catch_up(laptop, url, TOKEN)["added"] == 2
            assert laptop.where_is("forklift").location == "loading bay"
        import urllib.error
        with pytest.raises(urllib.error.HTTPError) as err:
            catch_up(laptop, url, "wrong")
        assert err.value.code == 401
    finally:
        server.shutdown()


def test_ask_sends_only_local_events_to_model(tmp_path) -> None:
    import json, threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from handoff import ask

    seen = {}

    class Fake(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):  # noqa: N802
            seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            out = json.dumps({"model": "fake", "choices": [{"message": {"content": " In the loading bay. "}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

    fake = HTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=fake.serve_forever, daemon=True).start()
    try:
        with _hub(tmp_path) as hub:
            result = ask("Where is the package?", hub, base_url=f"http://127.0.0.1:{fake.server_address[1]}/v1", model="fake")
    finally:
        fake.shutdown()
    assert result == {"answer": "In the loading bay.", "model": "fake",
                      "base_url": f"http://127.0.0.1:{fake.server_address[1]}/v1", "events_used": 2}
    prompt = seen["body"]["messages"][1]["content"]
    assert "package unloaded" in prompt and "/tmp/f.jpg" not in prompt
    assert seen["body"]["temperature"] == 0
