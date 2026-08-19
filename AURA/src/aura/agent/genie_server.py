# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""OpenAI-compatible HTTP shim over Qualcomm Genie (Milestone 4, NPU path).

Genie (QAIRT) ships only CLI runners (``genie-t2t-run``) — no HTTP server — so
AURA's :class:`aura.agent.llm.LocalLLM` (which speaks the OpenAI
``/v1/chat/completions`` protocol) can't talk to the NPU directly. This module
is the bridge: a tiny **stdlib-only** HTTP server that renders chat messages
into the model's prompt template, shells out to ``genie-t2t-run`` on the NPU,
parses its output, and returns an OpenAI-shaped JSON response.

Stdlib-only on purpose: it must run on the bare on-device Python (the IQ8 /
VENTUNO Q has Python 3.x but no pip), so it uses ``http.server`` and
``subprocess`` — nothing from PyPI.

Run on the device (after the QAIRT aarch64 runtime + a v75 model bundle are in
place)::

    python3 -m aura.agent.genie_server \\
        --genie-bin  /opt/aura-llm/genie-t2t-run \\
        --genie-config /opt/aura-llm/genie_config.json \\
        --host 0.0.0.0 --port 8080

then point AURA at it: ``AURA_LLM_BASE_URL=http://<device-ip>:8080``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

# Qwen/ChatML template tokens — the format the bundled sample_prompt.txt uses.
_IM_START = "<|im_start|>"
_IM_END = "<|im_end|>"

# genie-t2t-run wraps generated text between these markers on stdout.
_BEGIN_RE = re.compile(r"\[BEGIN\]:?\s?(.*?)\[END\]", re.DOTALL)


def render_chatml(messages: list[dict[str, str]]) -> str:
    """Render OpenAI ``messages`` into a ChatML prompt for the model.

    Ends with an open assistant turn so the model continues from there.
    """
    parts = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        parts.append(f"{_IM_START}{role}\n{content}{_IM_END}")
    parts.append(f"{_IM_START}assistant\n")
    return "\n".join(parts)


def parse_genie_output(raw: str) -> str:
    """Extract the generated text from genie-t2t-run stdout.

    Prefers the ``[BEGIN]…[END]`` span; falls back to the stripped raw text so
    a marker format change degrades instead of returning empty.
    """
    match = _BEGIN_RE.search(raw)
    if match:
        return match.group(1).strip()
    return raw.strip()


class GenieRunner:
    """Invokes ``genie-t2t-run`` once per request and returns the completion."""

    def __init__(self, genie_bin: str, genie_config: str, *, timeout: float = 120.0,
                 cwd: str | None = None) -> None:
        self.genie_bin = genie_bin
        self.genie_config = genie_config
        self.timeout = timeout
        # genie configs reference bundle files by relative path, so run from the
        # bundle dir unless told otherwise.
        self.cwd = cwd or os.path.dirname(os.path.abspath(genie_config))

    def generate(self, prompt: str) -> str:
        proc = subprocess.run(
            [self.genie_bin, "-c", self.genie_config, "-p", prompt],
            capture_output=True, text=True, timeout=self.timeout, cwd=self.cwd,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"genie-t2t-run exited {proc.returncode}: {proc.stderr.strip()[:500]}"
            )
        return parse_genie_output(proc.stdout)


def _make_handler(runner: GenieRunner, model_id: str):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _send(self, code: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 (http.server API)
            # Minimal OpenAI /v1/models so clients can probe the endpoint.
            if self.path.rstrip("/") == "/v1/models":
                self._send(200, {"object": "list",
                                 "data": [{"id": model_id, "object": "model"}]})
            else:
                self._send(404, {"error": {"message": "not found"}})

        def do_POST(self) -> None:  # noqa: N802 (http.server API)
            if self.path.rstrip("/") != "/v1/chat/completions":
                self._send(404, {"error": {"message": "not found"}})
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length) or b"{}")
                prompt = render_chatml(req.get("messages", []))
                text = runner.generate(prompt)
            except Exception as exc:  # noqa: BLE001 — report as OpenAI-style error
                self._send(500, {"error": {"message": str(exc),
                                           "type": type(exc).__name__}})
                return

            self._send(200, {
                "id": f"chatcmpl-{int(time.time() * 1000)}",
                "object": "chat.completion",
                "model": req.get("model", model_id),
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }],
            })

        def log_message(self, *_: Any) -> None:  # keep stdout clean
            return

    return Handler


def build_server(host: str, port: int, runner: GenieRunner, *, model_id: str
                 ) -> ThreadingHTTPServer:
    """Create (but don't start) the HTTP server. Exposed for tests."""
    return ThreadingHTTPServer((host, port), _make_handler(runner, model_id))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aura-genie-server",
        description="OpenAI-compatible HTTP shim over Qualcomm Genie (NPU).",
    )
    parser.add_argument("--genie-bin", default=os.environ.get("AURA_GENIE_BIN", "genie-t2t-run"))
    parser.add_argument("--genie-config", required=True,
                        help="path to the bundle's genie_config.json")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--model", default=os.environ.get("AURA_LLM_MODEL", "qwen3-4b-npu"))
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args(argv)

    runner = GenieRunner(args.genie_bin, args.genie_config, timeout=args.timeout)
    server = build_server(args.host, args.port, runner, model_id=args.model)
    print(f"AURA Genie server on http://{args.host}:{args.port}  "
          f"(model={args.model}, bin={args.genie_bin})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
