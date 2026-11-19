"""End-to-end: ``quad-client detect/doctor --json`` exits 0 and parses."""

from __future__ import annotations

import json
import subprocess
import sys


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "quad_mcp_client.cli", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )


def test_detect_json_emits_valid_envelope() -> None:
    r = _run("detect", "--no-sdk-probe", "--json")
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert "chipset" in payload
    assert "available_runtimes" in payload


def test_doctor_json_emits_check_list() -> None:
    r = _run("doctor", "--json")
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert isinstance(payload, list) and len(payload) >= 5
    assert all("name" in c and "status" in c for c in payload)


def test_unoq_configure_emits_toml_stanza() -> None:
    r = _run("unoq", "configure", "192.168.1.42", "--user", "pi")
    assert r.returncode == 0, r.stderr
    assert "[target]" in r.stdout
    assert "host = \"192.168.1.42\"" in r.stdout


def test_unoq_help_lists_all_subcommands() -> None:
    r = _run("unoq", "--help")
    assert r.returncode == 0, r.stderr
    for cmd in ("status", "configure", "deploy", "firmware", "logs", "debug",
                "perf", "stability", "power", "app", "ota", "test"):
        assert cmd in r.stdout, f"missing subcommand in help: {cmd}"
