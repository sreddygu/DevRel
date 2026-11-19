"""test_settings_to_connect_test.py — end-to-end: values written into
``.claude/settings.json`` must be the same values that drive a successful
``connect-test`` invocation.

The CLAUDE.md connectivity-check procedure tells the agent to read
``mcpServers.quad`` out of settings.json and feed its transport/url/token-env
straight into ``connect-test``. Nothing previously verified that round trip —
``test_transport_settings.py`` checks the JSON shape in isolation, and
``test_cli.py``/``test_connect_test_cli.py`` check ``connect-test`` in
isolation. This file checks the seam between them.

Modified: 2026-07-16
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from quad_mcp_client.claude_code import ClaudeCodeProvisioner
from quad_mcp_client.claude_code.provisioner import TransportConfig
from quad_mcp_client.cli import app
from quad_mcp_client.connection import ConnectionProbeResult


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _quad_block(settings_path: Path) -> dict:
    settings = json.loads(settings_path.read_text())
    return settings["mcpServers"]["quad"]


class TestSseSettingsFeedConnectTest:
    def test_url_from_settings_reaches_probe(
        self, tmp_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prov = ClaudeCodeProvisioner()
        cfg = TransportConfig(
            transport="sse-http",
            sse_url="http://10.227.21.202:8000/mcp",
            sse_auth_token_env="QUAD_MCP_TOKEN",
        )
        prov.install(tmp_path, transport_config=cfg)

        quad = _quad_block(tmp_path / ".claude" / "settings.json")
        url = quad["transport"]["url"]
        token_env = quad["transport"]["headers"]["Authorization"].split(":")[-1].rstrip("}")

        captured: dict = {}

        def fake_probe(transport, **kwargs):
            captured.update(kwargs)
            return ConnectionProbeResult(ok=True, transport=transport)

        monkeypatch.setattr("quad_mcp_client.cli.probe", fake_probe)
        monkeypatch.setenv(token_env, "test-token-value")

        r = runner.invoke(
            app,
            [
                "connect-test", "sse-http",
                "--sse-url", url,
                "--auth-token", "test-token-value",
            ],
        )
        assert r.exit_code == 0
        assert captured["url"] == "http://10.227.21.202:8000/mcp"
        assert captured["auth_token"] == "test-token-value"

    def test_stdio_local_command_from_settings_reaches_probe(
        self, tmp_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prov = ClaudeCodeProvisioner()
        prov.install(tmp_path)  # default stdio-local

        quad = _quad_block(tmp_path / ".claude" / "settings.json")
        command = quad["command"]

        captured: dict = {}

        def fake_probe(transport, **kwargs):
            captured.update(kwargs)
            return ConnectionProbeResult(ok=True, transport=transport)

        monkeypatch.setattr("quad_mcp_client.cli.probe", fake_probe)
        r = runner.invoke(
            app, ["connect-test", "stdio-local", "--server-command", command]
        )
        assert r.exit_code == 0
        assert captured["command"] == command

    def test_stdio_ssh_host_user_from_settings_reach_probe(
        self, tmp_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prov = ClaudeCodeProvisioner()
        cfg = TransportConfig(
            transport="stdio-ssh", ssh_user="bob", ssh_host="snapdragon-dev.lan",
        )
        prov.install(tmp_path, transport_config=cfg)

        quad = _quad_block(tmp_path / ".claude" / "settings.json")
        assert "bob@snapdragon-dev.lan" in quad["args"]

        captured: dict = {}

        def fake_probe(transport, **kwargs):
            captured.update(kwargs)
            return ConnectionProbeResult(ok=True, transport=transport)

        monkeypatch.setattr("quad_mcp_client.cli.probe", fake_probe)
        r = runner.invoke(
            app,
            [
                "connect-test", "stdio-ssh",
                "--ssh-user", "bob",
                "--ssh-host", "snapdragon-dev.lan",
            ],
        )
        assert r.exit_code == 0
        assert captured["ssh_user"] == "bob"
        assert captured["ssh_host"] == "snapdragon-dev.lan"


class TestTokenEnvVarResolution:
    """The auth header in settings.json is a template string
    (``Bearer ${env:NAME}``) that Claude Code resolves at runtime — the
    agent instructions must extract ``NAME`` and pass its *value*, not the
    template, to ``--auth-token``. Guard the parsing shape."""

    def test_auth_header_template_names_the_env_var(self, tmp_path: Path) -> None:
        prov = ClaudeCodeProvisioner()
        cfg = TransportConfig(
            transport="sse-http",
            sse_url="https://hosted.mcp.cloud/mcp",
            sse_auth_token_env="QUAD_MCP_TOKEN",
        )
        prov.install(tmp_path, transport_config=cfg)

        quad = _quad_block(tmp_path / ".claude" / "settings.json")
        header = quad["transport"]["headers"]["Authorization"]
        assert header == "Bearer ${env:QUAD_MCP_TOKEN}"

    def test_no_token_env_configured_omits_headers_block(self, tmp_path: Path) -> None:
        prov = ClaudeCodeProvisioner()
        cfg = TransportConfig(transport="sse-http", sse_url="https://hosted.mcp.cloud/mcp")
        prov.install(tmp_path, transport_config=cfg)

        quad = _quad_block(tmp_path / ".claude" / "settings.json")
        assert "headers" not in quad["transport"]
