"""test_probe_dispatch_and_timeouts.py — coverage for gaps left in
``tests/test_connection.py``:

1. ``probe()`` dispatch only had a test for the *unknown*-transport branch —
   nothing proved it correctly routes ``stdio-local``/``stdio-ssh``/``sse-http``
   to the matching ``probe_*`` function with the right kwargs.
2. The SSH connection-timeout branch (``subprocess.TimeoutExpired``) in
   ``probe_stdio_ssh`` was untested.
3. The HTTP timeout branch (``httpx.TimeoutException``) in ``probe_sse_http``
   was untested.
4. ``httpx`` not installed at all (import-time fallback) was untested.

Modified: 2026-07-16
"""

from __future__ import annotations

import subprocess

import pytest

from devrel_client import connection
from devrel_client.connection import probe


class TestProbeDispatchRouting:
    """Each transport in probe() must call its matching probe_* function
    with the caller's kwargs — not just fall through to an error."""

    def test_stdio_local_routes_and_forwards_kwargs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict = {}

        def fake(**kwargs):
            captured.update(kwargs)
            return connection.ConnectionProbeResult(ok=True, transport="stdio-local")

        monkeypatch.setattr(connection, "probe_stdio_local", fake)
        result = probe("stdio-local", command="/usr/bin/python3")
        assert result.ok is True
        assert captured == {"command": "/usr/bin/python3"}

    def test_stdio_ssh_routes_and_forwards_kwargs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict = {}

        def fake(**kwargs):
            captured.update(kwargs)
            return connection.ConnectionProbeResult(ok=True, transport="stdio-ssh")

        monkeypatch.setattr(connection, "probe_stdio_ssh", fake)
        result = probe("stdio-ssh", ssh_user="bob", ssh_host="h")
        assert result.ok is True
        assert captured == {"ssh_user": "bob", "ssh_host": "h"}

    def test_sse_http_routes_and_forwards_kwargs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict = {}

        def fake(**kwargs):
            captured.update(kwargs)
            return connection.ConnectionProbeResult(ok=True, transport="sse-http")

        monkeypatch.setattr(connection, "probe_sse_http", fake)
        result = probe("sse-http", url="http://x/mcp", auth_token="t")
        assert result.ok is True
        assert captured == {"url": "http://x/mcp", "auth_token": "t"}


class TestProbeStdioSshTimeout:
    def test_ssh_connect_timeout_reports_clear_hint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="ssh", timeout=kwargs.get("timeout", 12))

        monkeypatch.setattr("subprocess.run", fake_run)
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/ssh")

        result = connection.probe_stdio_ssh(
            ssh_user="me", ssh_host="unreachable.example.com", timeout_s=3
        )
        assert result.ok is False
        assert "timed out" in result.error.lower()
        assert "unreachable.example.com" in result.hint


class TestProbeSseHttpTimeout:
    def test_timeout_exception_reports_clear_hint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import httpx

        class FakeClient:
            def __init__(self, *a, **kw):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def post(self, *a, **kw):
                raise httpx.TimeoutException("timed out")

            def get(self, *a, **kw):
                raise httpx.TimeoutException("timed out")

        monkeypatch.setattr("httpx.Client", FakeClient)
        result = connection.probe_sse_http("https://slow.example.com/mcp", timeout_s=2)
        assert result.ok is False
        assert "timed out" in result.error.lower()
        assert "slow.example.com" in result.hint


class TestProbeSseHttpNoHttpx:
    def test_missing_httpx_reports_install_hint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If httpx isn't installed, _try_mcp_initialize bails out (returns
        None) and the GET-fallback import must surface an actionable
        install hint rather than an ImportError traceback."""
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "httpx":
                raise ImportError("No module named 'httpx'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        result = connection.probe_sse_http("https://mcp.example.com/mcp")
        assert result.ok is False
        assert "httpx" in result.error.lower()
        assert "pip install" in result.hint
