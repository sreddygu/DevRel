"""Tests for the QuadClient SDK (quad_mcp_client.client).

Covers the parts testable without a live MCP server: transport resolution,
payload extraction (schema-compat), retry policy, auth, and the pagination
helper (via a fake in-memory client). A live end-to-end test belongs in the
sample scripts, not here.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from quad_mcp_client import (
    ClientAuth,
    QuadClient,
    QuadConnectionError,
    RetryPolicy,
    create_client,
)
from quad_mcp_client.client import _extract_payload, _resolve_transport


def _run(coro):
    """Drive a coroutine to completion (the client repo has no async plugin)."""
    return asyncio.run(coro)


# ── RetryPolicy ────────────────────────────────────────────────────────────────


def test_retry_backoff_is_exponential_and_capped() -> None:
    rp = RetryPolicy(base_delay_s=0.5, multiplier=2.0, max_delay_s=4.0)
    assert [rp.delay_for(n) for n in range(5)] == [0.5, 1.0, 2.0, 4.0, 4.0]


# ── ClientAuth ─────────────────────────────────────────────────────────────────


def test_auth_headers_bearer() -> None:
    assert ClientAuth(token="abc").headers == {"Authorization": "Bearer abc"}
    assert ClientAuth().headers == {}


def test_auth_from_env(monkeypatch) -> None:
    monkeypatch.setenv("QUAD_MCP_TOKEN", "tok")
    monkeypatch.setenv("QUAD_MCP_CA_BUNDLE", "/etc/ca.pem")
    a = ClientAuth.from_env()
    assert a.token == "tok"
    assert a.ca_bundle == "/etc/ca.pem"


# ── transport resolution ───────────────────────────────────────────────────────


def test_explicit_url_wins(monkeypatch) -> None:
    monkeypatch.delenv("QUAD_MCP_URL", raising=False)
    t = _resolve_transport(url="https://h:8000/mcp", command=None, args=None, auth=ClientAuth(token="x"))
    assert t.kind == "sse-http"
    assert t.url == "https://h:8000/mcp"
    assert t.auth.token == "x"


def test_explicit_command_wins() -> None:
    t = _resolve_transport(url=None, command="python", args=["-m", "quad.mcp.server"], auth=None)
    assert t.kind == "stdio-local"
    assert t.command == "python"


def test_env_url_used(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("QUAD_MCP_URL", "https://env-host/mcp")
    monkeypatch.chdir(tmp_path)  # no .claude/settings.json here
    t = _resolve_transport(url=None, command=None, args=None, auth=None)
    assert t.kind == "sse-http"
    assert t.url == "https://env-host/mcp"


def test_settings_json_http_discovered(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("QUAD_MCP_URL", raising=False)
    monkeypatch.setenv("QUAD_MCP_TOKEN", "sekret")
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "settings.json").write_text(json.dumps({
        "mcpServers": {"quad": {"transport": {
            "type": "http", "url": "https://disc/mcp",
            "headers": {"Authorization": "Bearer ${env:QUAD_MCP_TOKEN}"},
        }}}
    }))
    monkeypatch.chdir(tmp_path)
    t = _resolve_transport(url=None, command=None, args=None, auth=None)
    assert t.kind == "sse-http"
    assert t.url == "https://disc/mcp"
    assert t.auth.token == "sekret"  # ${env:...} expanded


def test_default_is_local_spawn(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("QUAD_MCP_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    t = _resolve_transport(url=None, command=None, args=None, auth=None)
    assert t.kind == "stdio-local"
    assert "quad.mcp.server" in t.args


# ── payload extraction (schema-compat) ─────────────────────────────────────────


class _Structured:
    def __init__(self, d: dict) -> None:
        self.structured_content = d
        self.content = []


class _Block:
    def __init__(self, text: str) -> None:
        self.text = text


class _TextResult:
    def __init__(self, text: str) -> None:
        self.structured_content = None
        self.content = [_Block(text)]


def test_extract_structured_content() -> None:
    assert _extract_payload(_Structured({"ok": True, "x": 1})) == {"ok": True, "x": 1}


def test_extract_text_json() -> None:
    assert _extract_payload(_TextResult(json.dumps({"a": 2}))) == {"a": 2}


def test_extract_text_non_json_wrapped() -> None:
    assert _extract_payload(_TextResult("not json")) == {"raw": "not json"}


# ── call_tool_dict + pagination with a fake fastmcp client ─────────────────────


class _FakeFastmcp:
    """Stands in for fastmcp.Client — records calls, returns canned results."""

    def __init__(self, responses: list) -> None:
        self._responses = responses
        self.calls: list = []

    async def call_tool(self, name, args):  # noqa: ANN001
        self.calls.append((name, args))
        return self._responses.pop(0)


@pytest.fixture
def connected_client() -> QuadClient:
    c = create_client(url="https://x/mcp")
    return c


async def _detect(client: QuadClient) -> dict:
    return await client.hardware_detect(platform="windows")


def test_call_tool_dict_parses(connected_client) -> None:
    connected_client._client = _FakeFastmcp([_Structured({"chipset": "X Elite"})])
    out = _run(_detect(connected_client))
    assert out["chipset"] == "X Elite"
    assert connected_client._client.calls[0][0] == "hardware_detect"


def test_not_connected_raises(connected_client) -> None:
    connected_client._client = None
    with pytest.raises(QuadConnectionError):
        _run(connected_client.call_tool("hardware_detect", {}))


async def _collect_search(client: QuadClient, **kw) -> list:
    return [m async for m in client.search_aihub(**kw)]


def test_search_aihub_paginates(connected_client) -> None:
    connected_client._client = _FakeFastmcp([
        _Structured({"matches": [{"id": "a"}, {"id": "b"}], "next_offset": 2}),
        _Structured({"matches": [{"id": "c"}], "next_offset": None}),
    ])
    ids = [m["id"] for m in _run(_collect_search(connected_client, query="mobilenet", page_size=2))]
    assert ids == ["a", "b", "c"]


def test_search_aihub_respects_max_results(connected_client) -> None:
    connected_client._client = _FakeFastmcp([
        _Structured({"matches": [{"id": "a"}, {"id": "b"}, {"id": "c"}], "next_offset": 3}),
    ])
    ids = [m["id"] for m in _run(_collect_search(connected_client, max_results=2))]
    assert ids == ["a", "b"]


def test_call_tool_retries_then_raises(connected_client) -> None:
    class _AlwaysFails:
        calls = 0

        async def call_tool(self, name, args):  # noqa: ANN001
            _AlwaysFails.calls += 1
            raise ConnectionError("boom")

    connected_client._client = _AlwaysFails()
    connected_client._retry = RetryPolicy(max_retries=2, base_delay_s=0.0)
    with pytest.raises(QuadConnectionError):
        _run(connected_client.call_tool("hardware_detect", {}))
    assert _AlwaysFails.calls == 3  # 1 initial + 2 retries


# ── QDQ bundle auto-unzip ────────────────────────────────────────────────────


class TestMaybeUnzipBundle:
    """download_artifact auto-unzips a QDQ ONNX bundle so the .onnx and its
    external-data sidecar (model.data) land together."""

    def test_unzips_onnx_and_sidecar(self, tmp_path: Path) -> None:
        import zipfile

        from quad_mcp_client.client import _maybe_unzip_bundle

        z = tmp_path / "mobilenetv2-12-static-qdq.zip"
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("mobilenetv2-12-static-qdq.onnx", b"\x08\x01GRAPH_refs_model.data")
            zf.writestr("model.data", b"W" * 4096)

        result = _maybe_unzip_bundle(z)
        assert result.name == "mobilenetv2-12-static-qdq.onnx"
        assert result.is_file()
        # The sidecar sits right beside the onnx (relative reference resolves).
        assert (result.parent / "model.data").is_file()
        assert not z.exists()  # zip dropped after extraction

    def test_non_zip_passthrough(self, tmp_path: Path) -> None:
        from quad_mcp_client.client import _maybe_unzip_bundle

        f = tmp_path / "model.onnx"
        f.write_bytes(b"ONNX")
        assert _maybe_unzip_bundle(f) == f
