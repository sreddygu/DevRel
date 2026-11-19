"""Tests for the standalone ``quad-client`` CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from quad_mcp_client.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# --- preview --------------------------------------------------------------


class TestPreview:
    def test_default_stdio_local(self, runner: CliRunner) -> None:
        r = runner.invoke(app, ["preview"])
        assert r.exit_code == 0
        parsed = json.loads(r.stdout)
        assert parsed["mcpServers"]["quad"]["command"] == "python"

    def test_stdio_ssh(self, runner: CliRunner) -> None:
        r = runner.invoke(
            app,
            ["preview", "--transport", "stdio-ssh", "--ssh-user", "alice", "--ssh-host", "x.lan"],
        )
        assert r.exit_code == 0
        parsed = json.loads(r.stdout)
        assert parsed["mcpServers"]["quad"]["command"] == "ssh"
        assert "alice@x.lan" in parsed["mcpServers"]["quad"]["args"]

    def test_sse_http(self, runner: CliRunner) -> None:
        r = runner.invoke(
            app,
            [
                "preview",
                "--transport", "sse-http",
                "--sse-url", "https://m.example.com/sse",
                "--sse-auth-token-env", "MY_TOKEN",
            ],
        )
        assert r.exit_code == 0
        parsed = json.loads(r.stdout)
        srv = parsed["mcpServers"]["quad"]
        assert srv["transport"]["type"] == "sse"
        assert srv["transport"]["url"] == "https://m.example.com/sse"

    def test_unknown_transport_returns_2(self, runner: CliRunner) -> None:
        r = runner.invoke(app, ["preview", "--transport", "bogus"])
        assert r.exit_code == 2


# --- status ---------------------------------------------------------------


class TestStatus:
    def test_status_when_nothing_installed(self, runner: CliRunner, tmp_path: Path) -> None:
        r = runner.invoke(app, ["status", "--project-root", str(tmp_path)])
        assert r.exit_code == 0
        assert "settings.json" in r.stdout
        assert "missing" in r.stdout

    def test_unknown_client_errors(self, runner: CliRunner) -> None:
        r = runner.invoke(app, ["status", "--client", "cursor"])
        assert r.exit_code == 2


# --- install --------------------------------------------------------------


class TestInstall:
    def test_stdio_local_install_with_skip_test(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        r = runner.invoke(
            app,
            [
                "install",
                "--project-root", str(tmp_path),
                "--skip-test",
            ],
        )
        assert r.exit_code == 0, r.stdout
        assert (tmp_path / ".claude" / "settings.json").is_file()

    def test_stdio_ssh_requires_user_and_host(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        r = runner.invoke(
            app,
            [
                "install",
                "--transport", "stdio-ssh",
                "--project-root", str(tmp_path),
            ],
        )
        assert r.exit_code == 2

    def test_sse_http_requires_url(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        r = runner.invoke(
            app,
            [
                "install",
                "--transport", "sse-http",
                "--project-root", str(tmp_path),
            ],
        )
        assert r.exit_code == 2

    def test_install_provisions_sse_settings(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        r = runner.invoke(
            app,
            [
                "install",
                "--transport", "sse-http",
                "--sse-url", "https://m.example.com/sse",
                "--project-root", str(tmp_path),
                "--skip-test",
            ],
        )
        assert r.exit_code == 0, r.stdout
        settings = json.loads(
            (tmp_path / ".claude" / "settings.json").read_text()
        )
        assert settings["mcpServers"]["quad"]["transport"]["type"] == "sse"


# --- connect-test ---------------------------------------------------------


class TestConnectTest:
    def test_unknown_transport(self, runner: CliRunner) -> None:
        r = runner.invoke(app, ["connect-test", "fake-transport"])
        assert r.exit_code == 2

    def test_stdio_ssh_requires_args(self, runner: CliRunner) -> None:
        r = runner.invoke(app, ["connect-test", "stdio-ssh"])
        assert r.exit_code == 2

    def test_sse_http_requires_url(self, runner: CliRunner) -> None:
        r = runner.invoke(app, ["connect-test", "sse-http"])
        assert r.exit_code == 2


# --- lightweight import ---------------------------------------------------


class TestLightweightImport:
    """The whole point of this package: importing ``quad_mcp_client.cli``
    should NOT pull in any heavy MCP server modules (fastmcp, numpy,
    pydantic, the QUAD adapter/runtime/compiler tree, etc.). Runs in a
    subprocess so the test process's module cache stays clean.
    """

    def test_client_cli_does_not_pull_heavy_modules(self) -> None:
        # Modules that would indicate the lightweight client accidentally
        # pulled in the full QUAD server stack.
        forbidden_prefixes = (
            "fastmcp",
            "numpy",
            "pydantic",
            "onnx",
            "fastapi",
            "uvicorn",
            "psutil",
            "jinja2",
            "structlog",
        )
        # Plus any quad.* server-side module — the client should never
        # need to import the QUAD server package.
        forbidden_quad_subs = (
            "quad.adapters",
            "quad.runtime",
            "quad.compiler",
            "quad.codegen",
            "quad.serve",
            "quad.profiler",
            "quad.mcp",
            "quad.tools",
            "quad.cli",
        )

        probe = (
            "import sys; "
            "import quad_mcp_client.cli; "
            f"forbidden = {forbidden_prefixes!r}; "
            f"forbidden_quad = {forbidden_quad_subs!r}; "
            "leaked = [m for m in sys.modules "
            "  if any(m == p or m.startswith(p + '.') for p in forbidden) "
            "  or any(m == q or m.startswith(q + '.') for q in forbidden_quad)]; "
            "print('|'.join(sorted(leaked)))"
        )
        result = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"probe failed: {result.stderr}"
        leaked = [m for m in result.stdout.strip().split("|") if m]
        assert not leaked, (
            "quad_mcp_client.cli unexpectedly pulled heavy modules in a fresh interpreter:\n"
            f"  {leaked}\n"
            "The whole point of this lightweight package is that it does NOT depend on "
            "fastmcp / numpy / pydantic / the QUAD server source tree."
        )
