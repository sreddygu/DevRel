"""Tests for the multi-transport settings.json templates + TransportConfig."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devrel_client.claude_code import (
    ClaudeCodeProvisioner,
    settings_template_sse,
    settings_template_ssh,
)
from devrel_client.claude_code.provisioner import TransportConfig

# --- stdio-ssh template ---------------------------------------------------


class TestSettingsTemplateSSH:
    def test_basic_ssh_settings(self) -> None:
        s = settings_template_ssh(ssh_user="alice", ssh_host="server.example.com")
        srv = s["mcpServers"]["devrel"]
        assert srv["command"] == "ssh"
        assert "alice@server.example.com" in srv["args"]
        # Default server command on remote
        assert "python -m devrel.mcp.server" in srv["args"]

    def test_custom_port(self) -> None:
        s = settings_template_ssh(ssh_user="x", ssh_host="y", ssh_port=2222)
        args = s["mcpServers"]["devrel"]["args"]
        # -p 2222 should appear
        assert "-p" in args
        assert "2222" in args

    def test_custom_key(self) -> None:
        s = settings_template_ssh(
            ssh_user="x", ssh_host="y", ssh_key="/home/me/.ssh/special_key"
        )
        args = s["mcpServers"]["devrel"]["args"]
        assert "-i" in args
        assert "/home/me/.ssh/special_key" in args

    def test_batch_mode_set(self) -> None:
        # BatchMode=yes prevents Claude Code from hanging on a password prompt
        s = settings_template_ssh(ssh_user="x", ssh_host="y")
        args = s["mcpServers"]["devrel"]["args"]
        assert "BatchMode=yes" in args

    def test_permissions_default(self) -> None:
        s = settings_template_ssh(ssh_user="x", ssh_host="y")
        for tool in (
            "mcp__devrel__hardware_detect",
            "mcp__devrel__convert_model",
            "mcp__devrel__profile_workload",
            "mcp__devrel__orchestrate_workload",
            "mcp__devrel__generate_code",
        ):
            assert tool in s["permissions"]["allow"]


# --- sse-http template ----------------------------------------------------


class TestSettingsTemplateSSE:
    def test_basic_sse_settings(self) -> None:
        s = settings_template_sse(url="https://mcp.example.com/sse")
        srv = s["mcpServers"]["devrel"]
        assert "transport" in srv
        assert srv["transport"]["type"] == "sse"
        assert srv["transport"]["url"] == "https://mcp.example.com/sse"
        # No subprocess command for SSE
        assert "command" not in srv

    def test_auth_token_env(self) -> None:
        s = settings_template_sse(
            url="https://mcp.example.com/sse",
            auth_token_env="DevRel_MCP_TOKEN",
        )
        headers = s["mcpServers"]["devrel"]["transport"]["headers"]
        assert "Authorization" in headers
        # Claude Code env-var substitution syntax
        assert "DevRel_MCP_TOKEN" in headers["Authorization"]

    def test_no_auth_token_omits_headers(self) -> None:
        s = settings_template_sse(url="https://mcp.example.com/sse")
        # No auth → no headers field
        srv = s["mcpServers"]["devrel"]
        assert "headers" not in srv["transport"]

    def test_mcp_path_emits_http_transport(self) -> None:
        # Streamable-HTTP servers expose /mcp and need type "http", not "sse".
        s = settings_template_sse(url="http://10.227.21.202:8000/mcp")
        assert s["mcpServers"]["devrel"]["transport"]["type"] == "http"

    def test_sse_path_still_emits_sse(self) -> None:
        s = settings_template_sse(url="https://mcp.example.com/sse")
        assert s["mcpServers"]["devrel"]["transport"]["type"] == "sse"

    def test_other_path_defaults_to_http(self) -> None:
        # Anything that isn't an explicit /sse endpoint → http.
        s = settings_template_sse(url="https://mcp.example.com/")
        assert s["mcpServers"]["devrel"]["transport"]["type"] == "http"

    def test_mcp_path_with_auth_header(self) -> None:
        s = settings_template_sse(
            url="http://10.227.21.202:8000/mcp",
            auth_token_env="DevRel_MCP_TOKEN",
        )
        transport = s["mcpServers"]["devrel"]["transport"]
        assert transport["type"] == "http"
        assert "DevRel_MCP_TOKEN" in transport["headers"]["Authorization"]


# --- TransportConfig dispatch --------------------------------------------


class TestTransportConfig:
    def test_stdio_local_default(self) -> None:
        cfg = TransportConfig()
        s = cfg.to_settings()
        assert s["mcpServers"]["devrel"]["command"] == "python"

    def test_stdio_ssh(self) -> None:
        cfg = TransportConfig(
            transport="stdio-ssh",
            ssh_user="bob",
            ssh_host="snapdragon-test.lan",
            ssh_port=22,
        )
        s = cfg.to_settings()
        assert s["mcpServers"]["devrel"]["command"] == "ssh"
        assert "bob@snapdragon-test.lan" in s["mcpServers"]["devrel"]["args"]

    def test_sse_http(self) -> None:
        cfg = TransportConfig(
            transport="sse-http",
            sse_url="https://hosted.mcp.cloud/sse",
        )
        s = cfg.to_settings()
        assert s["mcpServers"]["devrel"]["transport"]["type"] == "sse"
        assert s["mcpServers"]["devrel"]["transport"]["url"] == "https://hosted.mcp.cloud/sse"

    def test_unknown_raises(self) -> None:
        cfg = TransportConfig(transport="invalid")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="Unknown transport"):
            cfg.to_settings()


# --- Provisioner end-to-end with non-default transport -------------------


class TestProvisionerWithTransport:
    def test_install_with_ssh_transport(self, tmp_path: Path) -> None:
        prov = ClaudeCodeProvisioner()
        cfg = TransportConfig(
            transport="stdio-ssh",
            ssh_user="bob",
            ssh_host="server.example.com",
        )
        result = prov.install(tmp_path, transport_config=cfg)
        assert result.client == "claude_code"

        settings_file = tmp_path / ".claude" / "settings.json"
        settings = json.loads(settings_file.read_text())
        srv = settings["mcpServers"]["devrel"]
        assert srv["command"] == "ssh"
        assert "bob@server.example.com" in srv["args"]

    def test_install_with_sse_transport(self, tmp_path: Path) -> None:
        prov = ClaudeCodeProvisioner()
        cfg = TransportConfig(
            transport="sse-http",
            sse_url="https://hosted.mcp.com/sse",
            sse_auth_token_env="MY_TOKEN",
        )
        prov.install(tmp_path, transport_config=cfg)

        settings_file = tmp_path / ".claude" / "settings.json"
        settings = json.loads(settings_file.read_text())
        srv = settings["mcpServers"]["devrel"]
        assert srv["transport"]["type"] == "sse"
        assert srv["transport"]["url"] == "https://hosted.mcp.com/sse"
        assert "MY_TOKEN" in srv["transport"]["headers"]["Authorization"]

    def test_install_sse_merges_into_existing_settings(self, tmp_path: Path) -> None:
        # User already has a settings.json with their own keys + another MCP
        # server. Supplying server details must refresh devrel WITHOUT --force and
        # WITHOUT clobbering the user's other content.
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text(
            json.dumps(
                {
                    "mine": True,
                    "permissions": {"allow": ["Bash(ls *)"]},
                    "mcpServers": {"other": {"command": "node", "args": ["srv.js"]}},
                }
            )
        )

        prov = ClaudeCodeProvisioner()
        cfg = TransportConfig(
            transport="sse-http",
            sse_url="http://10.227.21.202:8000/mcp",
            sse_auth_token_env="DevRel_MCP_TOKEN",
        )
        result = prov.install(tmp_path, transport_config=cfg)

        merged = json.loads(settings_path.read_text())
        # devrel block added with the correct (http) transport + bearer header
        devrel = merged["mcpServers"]["devrel"]
        assert devrel["transport"]["type"] == "http"
        assert devrel["transport"]["url"] == "http://10.227.21.202:8000/mcp"
        assert "DevRel_MCP_TOKEN" in devrel["transport"]["headers"]["Authorization"]
        # user content preserved
        assert merged["mine"] is True
        assert merged["mcpServers"]["other"]["command"] == "node"
        # reported as written (updated), not skipped
        assert any("settings.json" in p for p in result.files_written)
        assert not any("settings.json" in p for p in result.files_skipped)

    def test_install_default_transport_unchanged(self, tmp_path: Path) -> None:
        # Backward-compat: install with no transport_config still produces
        # the original stdio-local settings shape
        prov = ClaudeCodeProvisioner()
        prov.install(tmp_path)

        settings_file = tmp_path / ".claude" / "settings.json"
        settings = json.loads(settings_file.read_text())
        srv = settings["mcpServers"]["devrel"]
        assert srv["command"] == "python"
        assert srv["args"] == ["-m", "devrel.mcp.server"]
