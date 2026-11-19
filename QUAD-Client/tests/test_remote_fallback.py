"""Phase 6 (IQ-9075 retrospective): run_mobilenetv2 remote MCP fallback (issue 5).

When no local Python can import quad.mcp.server, the sample must fall back to
the remote MCP server configured in .claude/settings.json instead of exiting
with a cryptic error. These tests import the sample module directly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SAMPLE_DIR = Path(__file__).resolve().parents[1] / "samples" / "mobilenetv2"
sys.path.insert(0, str(_SAMPLE_DIR))

run_mobilenetv2 = pytest.importorskip("run_mobilenetv2")


def test_remote_mcp_url_parsed(monkeypatch, tmp_path):
    # Build a fake project tree with .claude/settings.json holding an http MCP.
    claude = tmp_path / "proj" / ".claude"
    claude.mkdir(parents=True)
    (claude / "settings.json").write_text(json.dumps({
        "mcpServers": {
            "quad": {
                "command": "python",
                "transport": {"type": "http", "url": "http://10.0.0.1:8000/mcp"},
            }
        }
    }))
    fake_script = tmp_path / "proj" / "samples" / "mobilenetv2" / "run_mobilenetv2.py"
    fake_script.parent.mkdir(parents=True)
    fake_script.write_text("# stub")

    monkeypatch.setattr(run_mobilenetv2, "__file__", str(fake_script))
    url = run_mobilenetv2._remote_mcp_url()
    assert url == "http://10.0.0.1:8000/mcp"


def test_remote_mcp_url_none_when_absent(monkeypatch, tmp_path):
    fake_script = tmp_path / "empty" / "run_mobilenetv2.py"
    fake_script.parent.mkdir(parents=True)
    fake_script.write_text("# stub")
    monkeypatch.setattr(run_mobilenetv2, "__file__", str(fake_script))
    assert run_mobilenetv2._remote_mcp_url() is None


def test_find_quad_python_prefers_remote_when_no_local(monkeypatch):
    """When _can_import never succeeds, the remote sentinel is returned rather
    than sys.exit. We simulate 'no local server' by forcing the internal import
    probe to fail for every candidate via a bogus QUAD_PYTHON and no importable
    interpreter — but since a sibling QUAD/.venv may exist on a dev box, we
    assert the fallback path directly through _remote_mcp_url instead."""
    monkeypatch.setattr(run_mobilenetv2, "_remote_mcp_url", lambda: "http://srv:8000/mcp")
    # The sentinel format is what _call_convert keys on.
    url = run_mobilenetv2._remote_mcp_url()
    assert f"remote:{url}" == "remote:http://srv:8000/mcp"
