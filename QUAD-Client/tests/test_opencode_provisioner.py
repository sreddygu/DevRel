"""Tests for the opencode MCP client provisioner.

Mirrors tests/test_provisioner.py (the Claude Code provisioner tests).
The key contract: opencode reuses the *same* ``.claude/skills`` files
Claude Code uses (no opencode-specific copies), and discovers the QUAD
MCP server from ``opencode.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quad_mcp_client import MCPClientProvisioner, ProvisionResult, get_provisioner
from quad_mcp_client.claude_code.provisioner import TransportConfig
from quad_mcp_client.opencode import (
    OPENCODE_SCHEMA,
    OpenCodeProvisioner,
    merge_config,
    opencode_config,
    opencode_mcp_block,
)

# --- config.py ------------------------------------------------------------


class TestOpencodeConfig:
    def test_stdio_local_shape(self) -> None:
        cfg = opencode_config(TransportConfig(transport="stdio-local", adapter_mode="real"))
        assert cfg["$schema"] == OPENCODE_SCHEMA
        quad = cfg["mcp"]["quad"]
        assert quad["type"] == "local"
        # server_command + server_args from TransportConfig (incl. the -u flag)
        assert quad["command"][0] == "python"
        assert quad["command"][-3:] == ["-m", "quad.mcp.server"] or quad["command"][-2:] == [
            "-m",
            "quad.mcp.server",
        ]
        assert "-m" in quad["command"] and "quad.mcp.server" in quad["command"]
        assert quad["environment"]["QUAD_ADAPTER_MODE"] == "real"

    def test_instructions_default_to_claude_md(self) -> None:
        cfg = opencode_config(TransportConfig(transport="stdio-local"))
        assert cfg["instructions"] == ["CLAUDE.md"]

    def test_adapter_mode_propagates(self) -> None:
        cfg = opencode_config(TransportConfig(transport="stdio-local", adapter_mode="mock"))
        assert cfg["mcp"]["quad"]["environment"]["QUAD_ADAPTER_MODE"] == "mock"

    def test_stdio_ssh_becomes_local_ssh_command(self) -> None:
        block = opencode_mcp_block(
            TransportConfig(
                transport="stdio-ssh",
                ssh_user="alice",
                ssh_host="lab.example.com",
                ssh_port=2222,
                ssh_key="/home/alice/.ssh/id_ed25519",
            )
        )
        assert block["type"] == "local"
        cmd = block["command"]
        assert cmd[0] == "ssh"
        assert "-p" in cmd and "2222" in cmd
        assert "-i" in cmd and "/home/alice/.ssh/id_ed25519" in cmd
        assert "alice@lab.example.com" in cmd
        assert "BatchMode=yes" in cmd

    def test_stdio_ssh_omits_key_when_unset(self) -> None:
        block = opencode_mcp_block(
            TransportConfig(transport="stdio-ssh", ssh_user="bob", ssh_host="h")
        )
        assert "-i" not in block["command"]

    def test_sse_http_becomes_remote(self) -> None:
        block = opencode_mcp_block(
            TransportConfig(
                transport="sse-http",
                sse_url="https://mcp.example.com/sse",
                sse_auth_token_env="QUAD_MCP_TOKEN",
            )
        )
        assert block["type"] == "remote"
        assert block["url"] == "https://mcp.example.com/sse"
        assert block["headers"]["Authorization"] == "Bearer ${env:QUAD_MCP_TOKEN}"

    def test_sse_http_omits_headers_without_token(self) -> None:
        block = opencode_mcp_block(
            TransportConfig(transport="sse-http", sse_url="https://mcp.example.com/sse")
        )
        assert "headers" not in block

    def test_unknown_transport_raises(self) -> None:
        tc = TransportConfig(transport="stdio-local")
        tc.transport = "bogus"  # type: ignore[assignment]
        with pytest.raises(ValueError, match="Unknown transport"):
            opencode_mcp_block(tc)


# --- merge_config (non-destructive) ---------------------------------------


class TestMergeConfig:
    def test_preserves_user_provider_and_other_mcp(self) -> None:
        existing = {
            "$schema": "user-schema",
            "provider": {"anthropic": {"name": "X"}},
            "mcp": {"playwright": {"type": "local", "command": ["npx", "playwright"]}},
            "instructions": ["DESIGN.md"],
        }
        generated = opencode_config(TransportConfig(transport="stdio-local"))
        merged = merge_config(existing, generated)
        # user content untouched
        assert merged["provider"]["anthropic"]["name"] == "X"
        assert "playwright" in merged["mcp"]
        assert merged["$schema"] == "user-schema"  # not overwritten
        # quad added + instructions unioned
        assert "quad" in merged["mcp"]
        assert "DESIGN.md" in merged["instructions"]
        assert "CLAUDE.md" in merged["instructions"]

    def test_sets_schema_when_absent(self) -> None:
        merged = merge_config({}, opencode_config(TransportConfig(transport="stdio-local")))
        assert merged["$schema"] == OPENCODE_SCHEMA

    def test_no_duplicate_instructions(self) -> None:
        existing = {"instructions": ["CLAUDE.md"]}
        merged = merge_config(existing, opencode_config(TransportConfig(transport="stdio-local")))
        assert merged["instructions"].count("CLAUDE.md") == 1


# --- write_config (skip / merge / force) ----------------------------------


class TestWriteConfig:
    def test_skips_when_quad_present_and_no_merge_or_force(self, tmp_path: Path) -> None:
        from quad_mcp_client.opencode.config import write_config

        path = tmp_path / "opencode.json"
        path.write_text(json.dumps({"mcp": {"quad": {"type": "remote", "url": "old"}}}))
        cfg = opencode_config(TransportConfig(transport="sse-http", sse_url="new"))
        assert write_config(path, config=cfg) is False
        # untouched
        assert json.loads(path.read_text())["mcp"]["quad"]["url"] == "old"

    def test_merge_refreshes_quad_and_keeps_user_config(self, tmp_path: Path) -> None:
        from quad_mcp_client.opencode.config import write_config

        path = tmp_path / "opencode.json"
        path.write_text(
            json.dumps(
                {
                    "provider": {"anthropic": {"name": "X"}},
                    "mcp": {
                        "quad": {"type": "remote", "url": "http://old:8000/mcp"},
                        "other": {"type": "local", "command": ["npx", "srv"]},
                    },
                }
            )
        )
        cfg = opencode_config(
            TransportConfig(transport="sse-http", sse_url="http://new:9000/mcp")
        )
        assert write_config(path, config=cfg, merge=True) is True

        result = json.loads(path.read_text())
        # quad refreshed to the new URL
        assert result["mcp"]["quad"]["url"] == "http://new:9000/mcp"
        # user content preserved
        assert result["provider"]["anthropic"]["name"] == "X"
        assert result["mcp"]["other"]["command"] == ["npx", "srv"]


# --- provisioner.install / status / uninstall -----------------------------


class TestOpenCodeProvisioner:
    def test_factory_returns_opencode_provisioner(self) -> None:
        prov = get_provisioner("opencode")
        assert isinstance(prov, OpenCodeProvisioner)
        assert isinstance(prov, MCPClientProvisioner)
        assert prov.name == "opencode"

    def test_install_writes_config_and_skills(self, tmp_path: Path) -> None:
        prov = OpenCodeProvisioner()
        result = prov.install(
            tmp_path, transport_config=TransportConfig(transport="stdio-local", adapter_mode="mock")
        )
        assert isinstance(result, ProvisionResult)
        cfg_path = tmp_path / "opencode.json"
        assert cfg_path.is_file()
        parsed = json.loads(cfg_path.read_text())
        assert parsed["mcp"]["quad"]["environment"]["QUAD_ADAPTER_MODE"] == "mock"
        # opencode globs <name>/SKILL.md — the dir form MUST be present
        dir_skills = list((tmp_path / ".claude" / "skills").glob("*/SKILL.md"))
        assert len(dir_skills) >= 10

    def test_install_defaults_to_stdio_local(self, tmp_path: Path) -> None:
        prov = OpenCodeProvisioner()
        prov.install(tmp_path)
        parsed = json.loads((tmp_path / "opencode.json").read_text())
        assert parsed["mcp"]["quad"]["type"] == "local"

    def test_install_idempotent_without_force(self, tmp_path: Path) -> None:
        prov = OpenCodeProvisioner()
        prov.install(tmp_path)
        result2 = prov.install(tmp_path)  # no force
        # opencode.json already has mcp.quad -> skipped, not rewritten
        assert str(tmp_path / "opencode.json") in result2.files_skipped

    def test_install_force_remerges(self, tmp_path: Path) -> None:
        prov = OpenCodeProvisioner()
        prov.install(tmp_path)
        result2 = prov.install(tmp_path, force=True)
        assert str(tmp_path / "opencode.json") in result2.files_written

    def test_reconfig_with_details_refreshes_without_force(self, tmp_path: Path) -> None:
        # First provision with one server URL, then re-run with a NEW URL and no
        # --force: the quad block must update (mirrors the Claude Code merge fix).
        prov = OpenCodeProvisioner()
        prov.install(
            tmp_path,
            transport_config=TransportConfig(
                transport="sse-http", sse_url="http://old:8000/mcp"
            ),
        )
        result2 = prov.install(
            tmp_path,
            transport_config=TransportConfig(
                transport="sse-http", sse_url="http://new:9000/mcp"
            ),
        )
        cfg_path = tmp_path / "opencode.json"
        assert str(cfg_path) in result2.files_written
        assert str(cfg_path) not in result2.files_skipped
        assert json.loads(cfg_path.read_text())["mcp"]["quad"]["url"] == "http://new:9000/mcp"

    def test_status_reports_complete_install(self, tmp_path: Path) -> None:
        prov = OpenCodeProvisioner()
        prov.install(tmp_path)
        s = prov.status(tmp_path)
        assert s["client"] == "opencode"
        assert s["settings_exists"] is True
        assert s["skills_dir_exists"] is True
        assert s["installed_skill_count"] == s["bundled_skill_count"]
        assert s["missing_skills"] == []

    def test_status_on_empty_dir(self, tmp_path: Path) -> None:
        prov = OpenCodeProvisioner()
        s = prov.status(tmp_path)
        assert s["settings_exists"] is False
        assert s["skills_dir_exists"] is False

    def test_uninstall_removes_only_config(self, tmp_path: Path) -> None:
        prov = OpenCodeProvisioner()
        prov.install(tmp_path)
        result = prov.uninstall(tmp_path)
        assert not (tmp_path / "opencode.json").exists()
        # skills are shared — left in place
        assert (tmp_path / ".claude" / "skills").is_dir()
        assert any("NOT removed" in n for n in result.notes)

    def test_preview_returns_valid_json(self) -> None:
        prov = OpenCodeProvisioner()
        preview = prov.render_config_preview()
        parsed = json.loads(preview)
        assert parsed["mcp"]["quad"]["type"] == "local"


# --- commands.py (opencode slash commands) --------------------------------


class TestOpencodeCommands:
    def test_short_description_drops_trigger_clause(self) -> None:
        from quad_mcp_client.opencode.commands import _short_description

        d = 'Use when the user asks "detect", or invokes /quad-detect. Probes the host.'
        assert _short_description(d, "quad-detect") == "Probes the host."

    def test_short_description_empty_falls_back(self) -> None:
        from quad_mcp_client.opencode.commands import _short_description

        assert _short_description("", "quad-detect") == "Run the quad-detect skill."

    def test_command_body_invokes_skill(self) -> None:
        from quad_mcp_client.opencode.commands import command_body

        body = command_body("quad-detect", "Use when X. Probes the host.")
        assert body.startswith("---\n")
        assert "description: Probes the host." in body
        assert "`quad-detect`" in body
        assert "$ARGUMENTS" in body

    def test_write_commands_creates_one_per_skill(self, tmp_path: Path) -> None:
        from quad_mcp_client.claude_code.skills import list_bundled_skills
        from quad_mcp_client.opencode.commands import write_commands

        written, skipped = write_commands(tmp_path, force=True)
        cmd_dir = tmp_path / ".opencode" / "commands"
        assert cmd_dir.is_dir()
        assert len(written) == len(list_bundled_skills())
        assert skipped == []
        # every generated file is valid frontmatter + body
        for f in cmd_dir.glob("*.md"):
            text = f.read_text()
            assert text.startswith("---\n")
            assert "skill to handle this request" in text

    def test_write_commands_idempotent_without_force(self, tmp_path: Path) -> None:
        from quad_mcp_client.opencode.commands import write_commands

        write_commands(tmp_path, force=True)
        written, skipped = write_commands(tmp_path, force=False)
        assert written == []
        assert len(skipped) > 0

    def test_remove_commands_cleans_generated_files(self, tmp_path: Path) -> None:
        from quad_mcp_client.opencode.commands import remove_commands, write_commands

        write_commands(tmp_path, force=True)
        removed = remove_commands(tmp_path)
        assert len(removed) > 0
        assert not (tmp_path / ".opencode" / "commands").exists()

    def test_provisioner_install_writes_commands(self, tmp_path: Path) -> None:
        prov = OpenCodeProvisioner()
        prov.install(tmp_path)
        cmd_dir = tmp_path / ".opencode" / "commands"
        assert (cmd_dir / "quad-detect.md").is_file()

    def test_provisioner_uninstall_removes_commands(self, tmp_path: Path) -> None:
        prov = OpenCodeProvisioner()
        prov.install(tmp_path)
        prov.uninstall(tmp_path)
        assert not (tmp_path / ".opencode" / "commands" / "quad-detect.md").exists()
