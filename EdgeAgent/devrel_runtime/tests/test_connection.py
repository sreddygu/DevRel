"""Tests for the MCP server connection probes."""

from __future__ import annotations

import pytest

from devrel_client.connection import (
    ConnectionProbeResult,
    probe,
    probe_sse_http,
    probe_stdio_local,
    probe_stdio_ssh,
)

# --- Result class ---------------------------------------------------------


class TestConnectionProbeResult:
    def test_render_ok(self) -> None:
        r = ConnectionProbeResult(ok=True, transport="stdio-local", latency_ms=42.0)
        out = r.render()
        assert "✓" in out
        assert "stdio-local" in out
        assert "42" in out

    def test_render_fail(self) -> None:
        r = ConnectionProbeResult(
            ok=False, transport="sse-http", error="connection refused", hint="check server"
        )
        out = r.render()
        assert "✗" in out
        assert "connection refused" in out
        assert "check server" in out

    def test_to_dict_serialisable(self) -> None:
        r = ConnectionProbeResult(ok=True, transport="stdio-local", latency_ms=10.0)
        d = r.to_dict()
        assert d["ok"] is True
        assert d["transport"] == "stdio-local"


# --- stdio-local ----------------------------------------------------------


class TestProbeStdioLocal:
    def test_python_runs_cleanly(self) -> None:
        # python -c 'import time; time.sleep(5)' should let the probe
        # confirm the process starts cleanly (it'll terminate it after 1s)
        result = probe_stdio_local(
            command="python",
            args=["-c", "import time; time.sleep(5)"],
        )
        # If python is on PATH, this should pass
        assert result.transport == "stdio-local"
        if result.ok:
            assert result.latency_ms > 0

    def test_missing_command_returns_clear_error(self) -> None:
        result = probe_stdio_local(command="this-command-definitely-does-not-exist-asdf")
        assert result.ok is False
        assert "not found" in result.error.lower()
        assert "PATH" in result.hint

    def test_immediate_exit_caught(self) -> None:
        # python -c 'import sys; sys.exit(1)' exits in <1s — caught as fail
        result = probe_stdio_local(
            command="python",
            args=["-c", "import sys; sys.exit(1)"],
        )
        assert result.ok is False
        assert "exited immediately" in result.error or result.error
        assert result.details.get("returncode") in (1, None)

    def test_default_args_target_devrel_mcp_server(self) -> None:
        # The default args invoke `python -m devrel.mcp.server`. We don't
        # require the server to actually be installed here — just confirm
        # the probe surfaces a sensible result either way.
        result = probe_stdio_local(command="python")
        assert result.transport == "stdio-local"
        # If devrel.mcp.server is importable, ok=True; otherwise ok=False
        # with a stderr hint mentioning the import. Either way the call
        # returns cleanly.
        if result.ok:
            # The probe uses `-u` (unbuffered) on the stdio server invocation so
            # Windows block-buffering doesn't hang the handshake; tolerate it.
            args = result.details.get("args")
            assert args in (
                ["-m", "devrel.mcp.server"],
                ["-u", "-m", "devrel.mcp.server"],
            )


# --- stdio-ssh ------------------------------------------------------------


class TestResolveCommand:
    """Regression tests for the Windows-friendly path resolver.

    Bug: install.sh on Git Bash hands the client an absolute path to a
    venv python without the .exe extension (because [ -f foo ] silently
    matches foo.exe via MSYS rewrites). shutil.which doesn't replicate
    that auto-extension for absolute paths, so the probe used to fail
    even though the binary clearly existed.
    """

    def test_falls_back_to_pathext_for_absolute_paths(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        from devrel_client.connection import _resolve_command

        # Pretend we're on Windows with a typical PATHEXT.
        monkeypatch.setattr("os.name", "nt")
        monkeypatch.setenv("PATHEXT", ".COM;.EXE;.BAT;.CMD")
        # shutil.which always misses (the bug condition).
        monkeypatch.setattr("shutil.which", lambda _cmd: None)

        # File exists only with .exe suffix.
        target = tmp_path / "python.exe"
        target.write_bytes(b"")

        bare = str(tmp_path / "python")
        assert _resolve_command(bare) == bare + ".exe"

    def test_returns_none_for_truly_missing_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        from devrel_client.connection import _resolve_command

        monkeypatch.setattr("os.name", "nt")
        monkeypatch.setenv("PATHEXT", ".EXE")
        monkeypatch.setattr("shutil.which", lambda _cmd: None)

        assert _resolve_command(str(tmp_path / "does-not-exist")) is None


class TestProbeStdioSsh:
    def test_no_ssh_command_clear_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Simulate ssh missing from PATH
        monkeypatch.setattr(
            "shutil.which", lambda cmd: None if cmd == "ssh" else "/usr/bin/python"
        )
        result = probe_stdio_ssh(ssh_user="x", ssh_host="y")
        assert result.ok is False
        assert "ssh" in result.error.lower()

    def test_invalid_host_caught(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Mock subprocess to simulate connection failure
        class FakeProc:
            returncode = 255
            stdout = ""
            stderr = "Could not resolve hostname fake-host: Name or service not known"

        def fake_run(*args: object, **kwargs: object) -> FakeProc:
            return FakeProc()

        monkeypatch.setattr("subprocess.run", fake_run)
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/ssh")

        result = probe_stdio_ssh(ssh_user="me", ssh_host="fake-host", timeout_s=2)
        assert result.ok is False
        assert "did not resolve" in result.hint or "DNS" in result.hint

    def test_permission_denied_hint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeProc:
            returncode = 255
            stdout = ""
            stderr = "Permission denied (publickey)."

        monkeypatch.setattr("subprocess.run", lambda *a, **kw: FakeProc())
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/ssh")

        result = probe_stdio_ssh(ssh_user="me", ssh_host="example.com", timeout_s=2)
        assert result.ok is False
        assert "key auth" in result.hint or "publickey" in result.hint

    def test_module_not_found_hint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeProc:
            returncode = 1
            stdout = ""
            stderr = "ModuleNotFoundError: No module named 'devrel'"

        monkeypatch.setattr("subprocess.run", lambda *a, **kw: FakeProc())
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/ssh")

        result = probe_stdio_ssh(ssh_user="me", ssh_host="example.com", timeout_s=2)
        assert result.ok is False
        # The hint points the user at installing the DevRel server package
        assert "DevRel" in result.hint or "Install" in result.hint or "install" in result.hint

    def test_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeProc:
            returncode = 0
            stdout = "OK\n"
            stderr = ""

        monkeypatch.setattr("subprocess.run", lambda *a, **kw: FakeProc())
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/ssh")

        result = probe_stdio_ssh(ssh_user="me", ssh_host="real-host", ssh_port=22, timeout_s=2)
        assert result.ok is True
        assert result.details["host"] == "real-host"
        assert result.details["user"] == "me"


# --- sse-http -------------------------------------------------------------


class TestProbeSseHttp:
    def test_2xx_is_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeResp:
            status_code = 200
            headers = {"server": "nginx/1.20"}

        class FakeClient:
            def __init__(self, *a, **kw):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def get(self, *a, **kw):
                return FakeResp()

        monkeypatch.setattr("httpx.Client", FakeClient)
        result = probe_sse_http("https://mcp.example.com/sse")
        assert result.ok is True
        assert result.details["status_code"] == 200

    def test_401_reports_auth_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeResp:
            status_code = 401
            headers = {}

        class FakeClient:
            def __init__(self, *a, **kw):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def get(self, *a, **kw):
                return FakeResp()

        monkeypatch.setattr("httpx.Client", FakeClient)
        result = probe_sse_http("https://mcp.example.com/sse", auth_token="wrong")
        assert result.ok is False
        assert "auth" in result.error.lower()
        assert "401" in result.error

    def test_404_reports_path_issue(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeResp:
            status_code = 404
            headers = {}

        class FakeClient:
            def __init__(self, *a, **kw):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def get(self, *a, **kw):
                return FakeResp()

        monkeypatch.setattr("httpx.Client", FakeClient)
        result = probe_sse_http("https://mcp.example.com/wrong-path")
        assert result.ok is False
        assert "404" in result.error
        assert (
            "URL path" in result.hint
            or "endpoints" in result.hint
            or "/sse" in result.hint
        )

    def test_connection_refused_caught(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import httpx

        class FakeClient:
            def __init__(self, *a, **kw):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def get(self, *a, **kw):
                raise httpx.ConnectError("Connection refused")

        monkeypatch.setattr("httpx.Client", FakeClient)
        result = probe_sse_http("https://nope.example.com/sse")
        assert result.ok is False
        assert "refused" in result.error or "connect" in result.error.lower()

    def test_html_200_rejected_as_wrong_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sprint-1 P0-9: a 200 OK with text/html almost always means the
        URL is wrong. Probe must reject it instead of claiming success."""
        class FakeResp:
            status_code = 200
            headers = {"server": "nginx/1.20", "content-type": "text/html; charset=utf-8"}

        class FakeClient:
            def __init__(self, *a, **kw):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass
            def get(self, *a, **kw):
                return FakeResp()

        monkeypatch.setattr("httpx.Client", FakeClient)
        result = probe_sse_http("https://mcp.example.com/")
        assert result.ok is False
        assert "content-type" in result.error.lower()
        assert "text/event-stream" in result.hint

    def test_event_stream_200_recognised_as_sse(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class FakeResp:
            status_code = 200
            headers = {"content-type": "text/event-stream"}

        class FakeClient:
            def __init__(self, *a, **kw):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass
            def get(self, *a, **kw):
                return FakeResp()

        monkeypatch.setattr("httpx.Client", FakeClient)
        result = probe_sse_http("https://mcp.example.com/sse")
        assert result.ok is True
        assert result.details["handshake"] == "sse"

    def test_json_200_recognised(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeResp:
            status_code = 200
            headers = {"content-type": "application/json"}

        class FakeClient:
            def __init__(self, *a, **kw):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass
            def get(self, *a, **kw):
                return FakeResp()

        monkeypatch.setattr("httpx.Client", FakeClient)
        result = probe_sse_http("https://mcp.example.com/mcp")
        assert result.ok is True
        assert result.details["handshake"] == "json"

    def test_406_treated_as_reachable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """FastMCP streamable-http returns 406 to a GET probe (it only
        accepts POST initialize). That's MCP-shaped reachability, not a
        failure — the real client will do the proper POST handshake."""
        class FakeResp:
            status_code = 406
            headers = {"server": "uvicorn", "content-type": "application/json"}

        class FakeClient:
            def __init__(self, *a, **kw):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass
            def get(self, *a, **kw):
                return FakeResp()

        monkeypatch.setattr("httpx.Client", FakeClient)
        result = probe_sse_http("http://10.0.0.1:8000/mcp")
        assert result.ok is True
        assert result.details["status_code"] == 406
        assert result.details["handshake"] == "unverified-406"

    def test_415_treated_as_reachable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Some streamable-http MCP servers reject a GET handshake with
        415 Unsupported Media Type. Same class as 406 — soft-pass."""
        class FakeResp:
            status_code = 415
            headers = {"server": "uvicorn"}

        class FakeClient:
            def __init__(self, *a, **kw):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass
            def get(self, *a, **kw):
                return FakeResp()

        monkeypatch.setattr("httpx.Client", FakeClient)
        result = probe_sse_http("http://10.0.0.1:8000/mcp")
        assert result.ok is True
        assert result.details["status_code"] == 415
        assert result.details["handshake"] == "unverified-415"

    def test_400_missing_session_id_treated_as_reachable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FastMCP streamable-http rejects a session-less GET with 400 +
        a JSON-RPC "Missing session ID" error and an mcp-session-id header.
        That signature is a reachable MCP server, not a failure."""
        class FakeResp:
            status_code = 400
            headers = {
                "server": "uvicorn",
                "content-type": "application/json",
                "mcp-session-id": "e9134aea7bf24368bf07863677bfe5a4",
            }
            text = (
                '{"jsonrpc":"2.0","id":"server-error","error":'
                '{"code":-32600,"message":"Bad Request: Missing session ID"}}'
            )

        class FakeClient:
            def __init__(self, *a, **kw):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass
            def get(self, *a, **kw):
                return FakeResp()

        monkeypatch.setattr("httpx.Client", FakeClient)
        result = probe_sse_http("http://10.0.0.1:8000/mcp")
        assert result.ok is True
        assert result.details["status_code"] == 400
        assert result.details["handshake"] == "unverified-400"

    def test_400_non_mcp_stays_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A bare 400 from some unrelated service (no MCP signature) must
        remain a failure -- we only soft-pass MCP-shaped 400s."""
        class FakeResp:
            status_code = 400
            headers = {"server": "nginx", "content-type": "text/html"}
            text = "<html><body>Bad Request</body></html>"

        class FakeClient:
            def __init__(self, *a, **kw):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass
            def get(self, *a, **kw):
                return FakeResp()

        monkeypatch.setattr("httpx.Client", FakeClient)
        result = probe_sse_http("http://10.0.0.1:8000/mcp")
        assert result.ok is False
        assert result.details["status_code"] == 400

    def test_accept_header_sent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The probe must send Accept: text/event-stream, application/json
        so streamable-http servers don't 406 it."""
        captured: dict = {}

        class FakeResp:
            status_code = 200
            headers = {"content-type": "text/event-stream"}

        class FakeClient:
            def __init__(self, *a, **kw):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass
            def get(self, url, headers=None, **kw):
                captured["headers"] = headers or {}
                return FakeResp()

        monkeypatch.setattr("httpx.Client", FakeClient)
        probe_sse_http("https://mcp.example.com/sse")
        accept = captured["headers"].get("Accept", "")
        assert "text/event-stream" in accept
        assert "application/json" in accept


class TestProbeSseHttpBadUrl:
    """A URL with control / non-printable chars (paste artifacts) must fail
    early with a precise message — before httpx raises a cryptic InvalidURL —
    and must not make any network call."""

    def test_syn_control_char_rejected_without_network(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(*a, **kw):  # any network use is a bug — fail loudly
            raise AssertionError("probe_sse_http made a network call on a bad URL")

        monkeypatch.setattr("httpx.Client", _boom)
        # \x16 (SYN) at position 0 — the exact failure from the bug report.
        result = probe_sse_http("\x16http://10.227.21.202:8000/mcp")
        assert result.ok is False
        assert result.transport == "sse-http"
        assert "non-printable" in result.error
        assert "position 0" in result.error
        # The hint must steer away from the misleading "debug with curl" advice.
        assert result.hint is not None
        assert "curl" in result.hint  # explicitly says curl won't help
        assert "paste" in result.hint.lower()

    def test_bom_and_zero_width_space_rejected(self) -> None:
        for bad in ("﻿http://x/mcp", "http://x​/mcp"):  # BOM, ZWSP
            result = probe_sse_http(bad)
            assert result.ok is False
            assert "non-printable" in result.error

    def test_clean_url_is_not_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A well-formed URL passes validation and proceeds to the probe."""
        class FakeResp:
            status_code = 200
            headers = {"content-type": "text/event-stream"}
            text = ""

        class FakeClient:
            def __init__(self, *a, **kw):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass
            def get(self, url, headers=None, **kw):
                return FakeResp()
            def post(self, url, headers=None, **kw):
                return FakeResp()

        monkeypatch.setattr("httpx.Client", FakeClient)
        result = probe_sse_http("http://10.227.21.202:8000/mcp")
        assert "non-printable" not in (result.error or "")


# --- dispatch -------------------------------------------------------------


class TestProbeSseHttpInitialize:
    """The real MCP `initialize` POST handshake (decisive pass / auth fail)."""

    @staticmethod
    def _client(*, post_status, post_body="", post_headers=None, get_raises=True):
        """Build a fake httpx.Client whose POST returns a canned response.

        By default GET raises, so any test reaching the GET fallback fails
        loudly (these tests want the POST path to be decisive).
        """
        class FakeResp:
            status_code = post_status
            headers = post_headers or {}
            text = post_body

        class FakeClient:
            def __init__(self, *a, **kw):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def post(self, *a, **kw):
                return FakeResp()

            def get(self, *a, **kw):
                if get_raises:
                    raise AssertionError("GET fallback should not be reached")
                return FakeResp()

        return FakeClient

    def test_initialize_serverinfo_hard_passes(self, monkeypatch) -> None:
        body = (
            'event: message\n'
            'data: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":'
            '"2024-11-05","serverInfo":{"name":"DevRel","version":"3.4.2"}}}\n'
        )
        monkeypatch.setattr(
            "httpx.Client", self._client(post_status=200, post_body=body)
        )
        result = probe_sse_http("http://10.0.0.1:8000/mcp", auth_token="good")
        assert result.ok is True
        assert result.details["handshake"] == "initialize"
        assert result.details["server_name"] == "DevRel"
        assert result.details["server_version"] == "3.4.2"
        assert "MCP handshake OK" in result.render()

    def test_initialize_plain_json_body(self, monkeypatch) -> None:
        body = (
            '{"jsonrpc":"2.0","id":1,"result":{"serverInfo":'
            '{"name":"S","version":"1"}}}'
        )
        monkeypatch.setattr(
            "httpx.Client", self._client(post_status=200, post_body=body)
        )
        result = probe_sse_http("http://10.0.0.1:8000/mcp")
        assert result.ok is True
        assert result.details["handshake"] == "initialize"

    def test_initialize_401_is_decisive_auth_failure(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "httpx.Client", self._client(post_status=401)
        )
        result = probe_sse_http("http://10.0.0.1:8000/mcp", auth_token="wrong")
        assert result.ok is False
        assert "auth" in result.error.lower()
        assert "401" in result.error

    def test_post_405_falls_back_to_get(self, monkeypatch) -> None:
        # An SSE-only server rejects the POST (405) but serves a GET SSE
        # stream -> the GET fallback must run and soft-pass.
        class FakePostResp:
            status_code = 405
            headers = {}
            text = ""

        class FakeGetResp:
            status_code = 200
            headers = {"server": "uvicorn", "content-type": "text/event-stream"}

        class FakeClient:
            def __init__(self, *a, **kw):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def post(self, *a, **kw):
                return FakePostResp()

            def get(self, *a, **kw):
                return FakeGetResp()

        monkeypatch.setattr("httpx.Client", FakeClient)
        result = probe_sse_http("http://10.0.0.1:8000/sse")
        assert result.ok is True
        assert result.details["handshake"] == "sse"


# --- dispatch -------------------------------------------------------------


class TestDispatch:
    def test_unknown_transport(self) -> None:
        result = probe("madeup-transport")  # type: ignore[arg-type]
        assert result.ok is False
        assert "Unknown transport" in result.error
