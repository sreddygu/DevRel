"""test_connect_test_cli.py — CLI-level coverage for ``quad-client connect-test``.

``tests/test_cli.py::TestConnectTest`` only exercises the three
argument-validation failures (unknown transport, missing ssh args, missing
sse url) — it never invokes the command on a *successful* probe, never
checks stdout rendering, exit codes on success vs. failure, or that CLI
flags are wired through to the right ``probe_*`` kwargs. This file closes
that gap by driving the Typer app end-to-end with the underlying
``quad_mcp_client.connection.probe`` dispatcher mocked.

Modified: 2026-07-16
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from quad_mcp_client.cli import app
from quad_mcp_client.connection import ConnectionProbeResult


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# --- exit codes on success / failure --------------------------------------


class TestConnectTestExitCodes:
    def test_success_exits_zero_and_prints_render(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_probe(transport, **kwargs):
            return ConnectionProbeResult(
                ok=True, transport=transport, latency_ms=12.3,
                details={"handshake": "initialize", "server_name": "QUAD", "server_version": "3.4.2"},
            )

        monkeypatch.setattr("quad_mcp_client.cli.probe", fake_probe)
        r = runner.invoke(
            app, ["connect-test", "sse-http", "--sse-url", "http://x/mcp"]
        )
        assert r.exit_code == 0
        assert "MCP handshake OK" in r.stdout
        assert "QUAD 3.4.2" in r.stdout

    def test_failure_exits_one_and_prints_hint(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_probe(transport, **kwargs):
            return ConnectionProbeResult(
                ok=False, transport=transport, error="connection refused",
                hint="check the server is running",
            )

        monkeypatch.setattr("quad_mcp_client.cli.probe", fake_probe)
        r = runner.invoke(
            app, ["connect-test", "sse-http", "--sse-url", "http://x/mcp"]
        )
        assert r.exit_code == 1
        assert "connection refused" in r.stdout
        assert "check the server is running" in r.stdout

    def test_validation_failure_exits_two_not_one(self, runner: CliRunner) -> None:
        """Argument-validation errors (exit 2) must stay distinct from a
        probe that ran and failed (exit 1) — callers/scripts branch on this."""
        r = runner.invoke(app, ["connect-test", "sse-http"])  # missing --sse-url
        assert r.exit_code == 2
        assert r.exit_code != 1


# --- flag -> probe kwarg wiring -------------------------------------------


class TestConnectTestArgumentWiring:
    """Confirm each transport's CLI flags reach the probe with the right
    kwarg names — a mismatch here silently no-ops a flag."""

    def test_stdio_local_passes_server_command_as_command(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict = {}

        def fake_probe(transport, **kwargs):
            captured.update(kwargs)
            return ConnectionProbeResult(ok=True, transport=transport)

        monkeypatch.setattr("quad_mcp_client.cli.probe", fake_probe)
        runner.invoke(
            app,
            ["connect-test", "stdio-local", "--server-command", "/path/to/python"],
        )
        assert captured == {"command": "/path/to/python"}

    def test_stdio_ssh_passes_all_ssh_kwargs(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict = {}

        def fake_probe(transport, **kwargs):
            captured.update(kwargs)
            return ConnectionProbeResult(ok=True, transport=transport)

        monkeypatch.setattr("quad_mcp_client.cli.probe", fake_probe)
        runner.invoke(
            app,
            [
                "connect-test", "stdio-ssh",
                "--ssh-user", "alice",
                "--ssh-host", "snapdragon.lan",
                "--ssh-port", "2222",
                "--ssh-key", "/home/alice/.ssh/id_ed25519",
                "--server", "python3 -m quad.mcp.server",
            ],
        )
        assert captured == {
            "ssh_user": "alice",
            "ssh_host": "snapdragon.lan",
            "ssh_port": 2222,
            "ssh_key": "/home/alice/.ssh/id_ed25519",
            "server_command": "python3 -m quad.mcp.server",
        }

    def test_sse_http_passes_url_and_token(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict = {}

        def fake_probe(transport, **kwargs):
            captured.update(kwargs)
            return ConnectionProbeResult(ok=True, transport=transport)

        monkeypatch.setattr("quad_mcp_client.cli.probe", fake_probe)
        runner.invoke(
            app,
            [
                "connect-test", "sse-http",
                "--sse-url", "http://10.227.21.202:8000/mcp",
                "--auth-token", "s3cr3t",
            ],
        )
        assert captured == {
            "url": "http://10.227.21.202:8000/mcp",
            "auth_token": "s3cr3t",
        }

    def test_sse_http_auth_token_optional(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict = {}

        def fake_probe(transport, **kwargs):
            captured.update(kwargs)
            return ConnectionProbeResult(ok=True, transport=transport)

        monkeypatch.setattr("quad_mcp_client.cli.probe", fake_probe)
        runner.invoke(
            app, ["connect-test", "sse-http", "--sse-url", "http://x/mcp"]
        )
        assert captured == {"url": "http://x/mcp", "auth_token": None}
