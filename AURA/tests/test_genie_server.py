# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""Tests for the Genie OpenAI shim (aura.agent.genie_server).

The pure helpers (ChatML rendering, output parsing) are tested directly. The
end-to-end path runs the real HTTP server against a *fake* ``genie-t2t-run``
(a small Python script that emits the ``[BEGIN]…[END]`` format), so no NPU or
QAIRT runtime is needed. Stdlib-only — runs on the base install.
"""

from __future__ import annotations

import json
import sys
import threading
import urllib.request
from http.client import HTTPConnection

from aura.agent.genie_server import (
    GenieRunner,
    build_server,
    parse_genie_output,
    render_chatml,
)

# A stand-in for genie-t2t-run: parses "-p <prompt>", echoes a canned reply in
# the same [BEGIN]…[END] envelope the real binary uses.
_FAKE_GENIE = """\
import sys
p = ""
a = sys.argv[1:]
for i, tok in enumerate(a):
    if tok == "-p" and i + 1 < len(a):
        p = a[i + 1]
# prove the prompt was templated by including whether the assistant turn opened
opened = "assistant" in p
print("Using libGenie.so version 2.47")
print("[BEGIN]: The answer is 42.[END]")
sys.stderr.write("open=%s\\n" % opened)
"""


def test_render_chatml_wraps_roles_and_opens_assistant() -> None:
    out = render_chatml([
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "hi"},
    ])
    assert "<|im_start|>system\nbe brief<|im_end|>" in out
    assert "<|im_start|>user\nhi<|im_end|>" in out
    assert out.rstrip().endswith("<|im_start|>assistant")  # open turn for gen


def test_parse_genie_output_extracts_begin_end() -> None:
    raw = "load logs...\n[BEGIN]: Hello world [END]\nmore logs"
    assert parse_genie_output(raw) == "Hello world"


def test_parse_genie_output_fallback_when_no_markers() -> None:
    assert parse_genie_output("  just text  ") == "just text"


def _write_fake_genie(tmp_path):
    script = tmp_path / "fake_genie.py"
    script.write_text(_FAKE_GENIE, encoding="utf-8")
    cfg = tmp_path / "genie_config.json"
    cfg.write_text("{}", encoding="utf-8")
    # Runner invokes [genie_bin, "-c", cfg, "-p", prompt]; we need python to run
    # the .py, so wrap by pointing genie_bin at a launcher via GenieRunner subclass.
    return script, cfg


class _PyGenieRunner(GenieRunner):
    """GenieRunner that runs the fake .py script through the Python interpreter."""

    def generate(self, prompt: str) -> str:  # type: ignore[override]
        import subprocess
        proc = subprocess.run(
            [sys.executable, self.genie_bin, "-c", self.genie_config, "-p", prompt],
            capture_output=True, text=True, timeout=self.timeout, cwd=self.cwd,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"exit {proc.returncode}: {proc.stderr[:200]}")
        from aura.agent.genie_server import parse_genie_output as _p
        return _p(proc.stdout)


def _serve(server):
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return t


def test_end_to_end_chat_completion(tmp_path) -> None:
    script, cfg = _write_fake_genie(tmp_path)
    runner = _PyGenieRunner(str(script), str(cfg))
    server = build_server("127.0.0.1", 0, runner, model_id="qwen3-4b-npu")
    port = server.server_address[1]
    _serve(server)
    try:
        payload = json.dumps({
            "model": "qwen3-4b-npu",
            "messages": [{"role": "user", "content": "What is the answer?"}],
        }).encode()
        conn = HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request("POST", "/v1/chat/completions", body=payload,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()
    finally:
        server.shutdown()
        server.server_close()

    assert resp.status == 200
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["content"] == "The answer is 42."
    assert data["choices"][0]["message"]["role"] == "assistant"


def test_models_endpoint(tmp_path) -> None:
    script, cfg = _write_fake_genie(tmp_path)
    server = build_server("127.0.0.1", 0, _PyGenieRunner(str(script), str(cfg)),
                          model_id="qwen3-4b-npu")
    port = server.server_address[1]
    _serve(server)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=10) as r:
            data = json.loads(r.read())
    finally:
        server.shutdown()
        server.server_close()
    assert data["data"][0]["id"] == "qwen3-4b-npu"
