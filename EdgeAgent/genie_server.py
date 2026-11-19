#!/usr/bin/env python3
r"""genie_server.py -- a tiny OpenAI-compatible HTTP shim around genie-t2t-run.

Why this exists: Qualcomm's Genie runtime (which runs an LLM on the Hexagon NPU)
ships only as a CLI -- `genie-t2t-run` -- with NO built-in HTTP server. Our
agent (`agent.py`) talks to an OpenAI-compatible `/v1/chat/completions`
endpoint. This shim bridges the two: it accepts the agent's HTTP requests,
flattens the chat messages into the model's prompt format, invokes
`genie-t2t-run` against a Genie bundle (running on the NPU), parses the
generated text out of stdout, and returns it in OpenAI response shape.

Result: the SAME `agent.py` that talks to llama.cpp (CPU) now talks to the
Hexagon NPU -- you only change `--base-url` to point at this shim.

    XElite NPU:  python genie_server.py --bundle C:\path\genie_bundle --model-name genie --port 8081
    then:        python agent.py --base-url http://127.0.0.1:8081 --model genie -v

Designed for Snapdragon X Elite on Windows (HTP v73), but works anywhere
`genie-t2t-run` runs. Stdlib only (http.server / subprocess / json).

Prompt formats per the Qualcomm llm_on_genie tutorial. Default is Llama 3.2.
Override with --chat-template if you use a different model family.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import traceback
from typing import Any


# --------------------------------------------------------------------------- #
# Chat templates: messages -> single prompt string the model was trained on.
# --------------------------------------------------------------------------- #
def template_llama3(messages: list[dict[str, str]]) -> str:
    """Llama 3.x / 3.2 instruct format."""
    out = ["<|begin_of_text|>"]
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        out.append(f"<|start_header_id|>{role}<|end_header_id|>\n\n{content}<|eot_id|>")
    out.append("<|start_header_id|>assistant<|end_header_id|>\n\n")
    return "".join(out)


def template_qwen(messages: list[dict[str, str]]) -> str:
    """Qwen2.5 / Qwen3 ChatML format."""
    out = []
    for m in messages:
        out.append(f"<|im_start|>{m.get('role','user')}\n{m.get('content','')}<|im_end|>\n")
    out.append("<|im_start|>assistant\n")
    return "".join(out)


def template_gemma(messages: list[dict[str, str]]) -> str:
    """Gemma 4 format as shipped in Qualcomm AI Hub Genie bundles.

    NOTE: AI Hub's Gemma-4 Genie bundle does NOT use the HuggingFace
    `<start_of_turn>...<end_of_turn>` markers. Its `tokenizer.json` defines the
    turn boundaries as the tokens `<|turn>` and `<turn|>`, and its
    `sample_prompt.txt` is:

        <bos><|turn>system
        You are a helpful AI assistant.<turn|>
        <|turn>user
        What is gravity?<turn|>
        <|turn>model

    Unlike stock Gemma, this format DOES carry a `system` turn, so we emit roles
    verbatim (system/user/model). `assistant` is normalized to `model`.
    """
    out = ["<bos>"]
    for m in messages:
        role = m.get("role", "user")
        if role == "assistant":
            role = "model"
        content = m.get("content", "")
        out.append(f"<|turn>{role}\n{content}<turn|>\n")
    out.append("<|turn>model\n")
    return "".join(out)


def template_plain(messages: list[dict[str, str]]) -> str:
    """Fallback: no special tokens, just role-prefixed lines."""
    out = []
    for m in messages:
        out.append(f"{m.get('role','user').upper()}: {m.get('content','')}")
    out.append("ASSISTANT:")
    return "\n".join(out)


TEMPLATES = {
    "llama3": template_llama3,
    "qwen": template_qwen,
    "gemma": template_gemma,
    "plain": template_plain,
}


# --------------------------------------------------------------------------- #
# Parse genie-t2t-run stdout -> just the generated text.
# --------------------------------------------------------------------------- #
# genie-t2t-run prints banner/diagnostic lines, then the generation wrapped
# between `[BEGIN]:` and `[END]` markers. Extract that; fall back gracefully.
_BEGIN_END = re.compile(r"\[BEGIN\]:(.*?)\[END\]", re.DOTALL)


def parse_genie_output(stdout: str) -> str:
    m = _BEGIN_END.search(stdout)
    if m:
        return m.group(1).strip()
    # Fallback: drop obvious diagnostic lines, return the rest.
    lines = [
        ln for ln in stdout.splitlines()
        if ln.strip()
        and not ln.startswith("[")
        and "libGenie" not in ln
        and "Using" not in ln
    ]
    return "\n".join(lines).strip()


# --------------------------------------------------------------------------- #
# Call genie-t2t-run against the bundle.
# --------------------------------------------------------------------------- #
class GenieRunner:
    def __init__(self, *, binary: str, config: Path, template: str, timeout: float,
                 extra: list[str]):
        self.binary = binary
        self.config = config
        self.bundle_dir = config.parent
        self.template_fn = TEMPLATES[template]
        self.timeout = timeout
        self.extra = extra
        self._resolved_config_path = self._write_resolved_config()

    def _write_resolved_config(self) -> Path:
        """Create a temp config with absolute paths for bundle assets.

        In practice, Genie bundles use relative paths (tokenizer, ctx-bins, backend
        extension config). Depending on how `genie-t2t-run` is launched (service,
        different CWD, remote client), relying on CWD resolution is fragile.

        To make the server robust, rewrite those paths to absolute paths anchored
        at the bundle directory.
        """
        raw = json.loads(self.config.read_text(encoding="utf-8"))

        def abs_in_bundle(p: str) -> str:
            p = str(p)
            # Already absolute (Windows drive or UNC) -> keep.
            if re.match(r"^[A-Za-z]:[\\/]", p) or p.startswith("\\\\"):
                return p
            return str((self.bundle_dir / p).resolve())

        dialog = raw.get("dialog") or {}
        tokenizer = (dialog.get("tokenizer") or {})
        if "path" in tokenizer:
            tokenizer["path"] = abs_in_bundle(tokenizer["path"])

        engine = (dialog.get("engine") or {})
        backend = (engine.get("backend") or {})
        if "extensions" in backend:
            backend["extensions"] = abs_in_bundle(backend["extensions"])

        model = (engine.get("model") or {})
        if model.get("type") == "binary":
            binary_model = (model.get("binary") or {})
            ctx_bins = binary_model.get("ctx-bins")
            if isinstance(ctx_bins, list):
                binary_model["ctx-bins"] = [abs_in_bundle(x) for x in ctx_bins]

        # Write resolved config to a stable temp file (kept for server lifetime).
        fd, path_str = tempfile.mkstemp(prefix="genie_config_abs_", suffix=".json")
        os.close(fd)
        out = Path(path_str)
        out.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        return out

    def generate(self, messages: list[dict[str, str]]) -> str:
        prompt = self.template_fn(messages)
        # Write the prompt to a file -- avoids shell-quoting/newline pain that
        # the tutorial explicitly warns about (backtick-n on PowerShell, etc.).
        with tempfile.NamedTemporaryFile(
            "w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(prompt)
            prompt_path = f.name
        cmd = [self.binary, "-c", str(self._resolved_config_path), "--prompt_file", prompt_path] + self.extra
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout,
                encoding="utf-8", errors="replace",
                cwd=self.bundle_dir,
            )
        finally:
            try:
                Path(prompt_path).unlink()
            except OSError:
                pass
        if proc.returncode != 0:
            raise RuntimeError(
                f"genie-t2t-run exited {proc.returncode}\n"
                f"cmd: {' '.join(cmd)}\nstderr:\n{proc.stderr[-2000:]}"
            )
        return parse_genie_output(proc.stdout)


# --------------------------------------------------------------------------- #
# HTTP handler -- OpenAI-compatible /v1/models and /v1/chat/completions.
# --------------------------------------------------------------------------- #
def make_handler(runner: GenieRunner, model_name: str):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, obj: dict[str, Any]) -> None:
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # quieter console
            sys.stderr.write("[genie_server] " + (args[0] % args[1:]) + "\n")

        def do_GET(self):
            if self.path.rstrip("/") == "/v1/models":
                self._send(200, {
                    "object": "list",
                    "data": [{"id": model_name, "object": "model", "owned_by": "genie"}],
                })
            else:
                self._send(404, {"error": f"not found: {self.path}"})

        def do_POST(self):
            if self.path.rstrip("/") != "/v1/chat/completions":
                self._send(404, {"error": f"not found: {self.path}"})
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length) or b"{}")
                messages = req.get("messages", [])
                text = runner.generate(messages)
            except Exception as exc:  # noqa: BLE001 -- report any failure as JSON
                sys.stderr.write("[genie_server] ERROR during /v1/chat/completions\n")
                sys.stderr.write(f"[genie_server] request bytes: {length}\n")
                try:
                    sys.stderr.write(f"[genie_server] model: {req.get('model')}\n")
                    sys.stderr.write(f"[genie_server] messages: {len(messages)}\n")
                    if messages:
                        sys.stderr.write(f"[genie_server] last role: {messages[-1].get('role')}\n")
                        last_content = (messages[-1].get("content") or "")
                        sys.stderr.write(f"[genie_server] last content chars: {len(last_content)}\n")
                except Exception:  # noqa: BLE001
                    pass
                sys.stderr.write("".join(traceback.format_exception(exc))[-4000:] + "\n")
                self._send(500, {"error": str(exc)})
                return
            self._send(200, {
                "object": "chat.completion",
                "model": model_name,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }],
            })

    return Handler


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="OpenAI-compatible HTTP shim around genie-t2t-run (Genie LLM on NPU).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--bundle", type=Path,
                   help="Path to the genie_bundle folder (containing genie_config.json).")
    p.add_argument("--config", type=Path,
                   help="Path to genie_config.json (defaults to <bundle>/genie_config.json).")
    p.add_argument("--binary", default="genie-t2t-run",
                   help="genie-t2t-run executable (use genie-t2t-run.exe on Windows if not on PATH).")
    p.add_argument("--chat-template", choices=sorted(TEMPLATES), default="llama3",
                   help="Prompt format for the model family.")
    p.add_argument("--model-name", default="genie",
                   help="Model id reported to clients (use this as agent.py --model).")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8081)
    p.add_argument("--timeout", type=float, default=300.0, help="Per-generation timeout (s).")
    p.add_argument("--extra", default="",
                   help="Extra raw args appended to genie-t2t-run (string).")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    config = args.config
    if config is None:
        if args.bundle is None:
            sys.exit("error: provide --config or --bundle (to locate genie_config.json)")
        config = args.bundle / "genie_config.json"
    # Normalize to an absolute path so relative ctx-bins/tokenizer paths resolve
    # correctly even if the server is launched from a different CWD.
    config = config.resolve()
    if not config.exists():
        sys.exit(f"error: genie config not found: {config}")

    runner = GenieRunner(
        binary=args.binary, config=config, template=args.chat_template,
        timeout=args.timeout, extra=args.extra.split() if args.extra.strip() else [],
    )
    handler = make_handler(runner, args.model_name)
    srv = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"genie_server: serving model '{args.model_name}' via {args.binary}")
    print(f"  config:   {config}")
    print(f"  template: {args.chat_template}")
    print(f"  endpoint: http://{args.host}:{args.port}/v1/chat/completions")
    print(f"  point the agent at it:  python agent.py --base-url http://{args.host}:{args.port} --model {args.model_name}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down.")
        srv.shutdown()


if __name__ == "__main__":
    main()
