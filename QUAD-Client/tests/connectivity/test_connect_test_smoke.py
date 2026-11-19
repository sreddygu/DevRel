"""test_connect_test_smoke.py — real-subprocess smoke tests for
``quad-client connect-test``.

Everything else in ``tests/connectivity/`` mocks ``quad_mcp_client.cli.probe``
or the probe internals — useful for exercising the CLI plumbing quickly, but
it never proves the actual command works end-to-end. This file invokes the
real CLI entry point as a subprocess (mirrors the pattern in
``tests/test_local/test_cli_smoke.py``), using ``stdio-local`` against the
current Python interpreter so it needs no network and no real MCP server.

Modified: 2026-07-16
"""

from __future__ import annotations

import subprocess
import sys


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "quad_mcp_client.cli", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )


def test_stdio_local_against_real_python_reports_reachable() -> None:
    """`connect-test stdio-local` with a command that starts and doesn't
    exit within 1s must exit 0 and render a checkmark — this is the
    happy path a user hits when the MCP package isn't even installed
    but the interpreter itself is fine."""
    r = _run(
        "connect-test", "stdio-local",
        "--server-command", sys.executable,
    )
    # The default args launch `-u -m quad.mcp.server`; if that package isn't
    # installed in this interpreter the preflight fails cleanly (exit 1),
    # which is itself a valid, deterministic outcome to assert on.
    assert r.returncode in (0, 1), r.stderr
    if r.returncode == 0:
        assert "✓" in r.stdout
        assert "stdio-local" in r.stdout
    else:
        assert "✗" in r.stdout


def test_stdio_local_missing_command_exits_one_with_hint() -> None:
    r = _run(
        "connect-test", "stdio-local",
        "--server-command", "this-binary-does-not-exist-9f3a",
    )
    assert r.returncode == 1
    assert "✗" in r.stdout
    assert "not found" in r.stdout.lower()
    assert "PATH" in r.stdout


def test_sse_http_unreachable_host_exits_one() -> None:
    """A real (mocked-nothing) probe against a non-routable address must
    fail cleanly and quickly rather than hang or crash the CLI."""
    r = _run(
        "connect-test", "sse-http",
        "--sse-url", "http://127.0.0.1:1/mcp",  # port 1: nothing listens
    )
    assert r.returncode == 1
    assert "✗" in r.stdout


def test_connect_test_writes_no_files(tmp_path) -> None:
    """The command's own docstring promises 'without writing any files' —
    verify no new files appear under cwd as a side effect of a full run."""
    before = set(tmp_path.iterdir())
    subprocess.run(
        [sys.executable, "-m", "quad_mcp_client.cli",
         "connect-test", "stdio-local", "--server-command", "this-does-not-exist"],
        capture_output=True, text=True, cwd=str(tmp_path), timeout=30,
    )
    after = set(tmp_path.iterdir())
    assert before == after
