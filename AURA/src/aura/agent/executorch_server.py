"""OpenAI-compatible HTTP shim over an ExecuTorch text-generation runner.

The pi agent harness speaks OpenAI Chat Completions, while ExecuTorch's example
LLM runner is a local command-line program. This module keeps that translation
inside one adapter: it renders chat messages and tool schemas into a compact
prompt, invokes the runner, and maps the model's JSON decision back to either
assistant text or an OpenAI-style tool call.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Protocol

from aura.agent.pipe_host import PipeHostManager

_RESPONSE_RE = re.compile(
    r"<AURA_RESPONSE>\s*(.*?)\s*</AURA_RESPONSE>",
    re.DOTALL | re.IGNORECASE,
)


class TextGenerator(Protocol):
    """Small seam implemented by the real runner and test fakes."""

    def generate(
        self,
        prompt: str,
        *,
        max_new_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str: ...


@dataclass(frozen=True)
class ModelDecision:
    """A normalized model result: final text or one tool invocation."""

    answer: str | None = None
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None

    @property
    def is_tool_call(self) -> bool:
        return self.tool_name is not None


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(part for part in parts if part)
    if content is None:
        return ""
    return str(content)


def render_agent_prompt(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> str:
    """Render an OpenAI chat request into a model-neutral agent prompt."""
    lines = [
        "You are AURA's local Gemma model running through ExecuTorch.",
        "Return exactly one response wrapped in <AURA_RESPONSE> tags.",
        "To answer normally, return:",
        '<AURA_RESPONSE>{"answer":"your answer"}</AURA_RESPONSE>',
    ]
    if tools:
        lines.extend([
            "To call one tool, return:",
            '<AURA_RESPONSE>{"tool":"tool_name","arguments":{"arg":"value"}}</AURA_RESPONSE>',
            "Use only a listed tool and only its declared arguments.",
            "Available tools:",
        ])
        for tool in tools:
            function = tool.get("function", tool)
            lines.append(json.dumps({
                "name": function.get("name", ""),
                "description": function.get("description", ""),
                "parameters": function.get("parameters", {}),
            }, separators=(",", ":")))
    else:
        lines.append("No tools are available for this turn.")

    lines.append("Conversation:")
    for message in messages:
        role = str(message.get("role", "user")).upper()
        if role == "ASSISTANT" and message.get("tool_calls"):
            lines.append(f"ASSISTANT_TOOL_CALLS: {json.dumps(message['tool_calls'])}")
            continue
        text = _message_text(message.get("content"))
        if role == "TOOL":
            tool_id = message.get("tool_call_id", "")
            lines.append(f"TOOL_RESULT[{tool_id}]: {text}")
        else:
            lines.append(f"{role}: {text}")
    lines.append("ASSISTANT:")
    return "\n".join(lines)


def _json_objects(text: str) -> list[dict[str, Any]]:
    decoder = json.JSONDecoder()
    objects: list[dict[str, Any]] = []
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            objects.append(value)
    return objects


def _is_model_decision(value: dict[str, Any]) -> bool:
    return "answer" in value or "tool" in value or (
        "name" in value and ("arguments" in value or "args" in value)
    )


def parse_model_decision(raw: str) -> ModelDecision:
    """Normalize Gemma output into final text or a single tool call."""
    tagged = _RESPONSE_RE.findall(raw)
    candidates = tagged or [raw]
    parsed: dict[str, Any] | None = None
    for candidate in reversed(candidates):
        try:
            value = json.loads(candidate.strip())
        except json.JSONDecodeError:
            value = None
        if isinstance(value, dict) and _is_model_decision(value):
            parsed = value
            break
        objects = _json_objects(candidate)
        for value in reversed(objects):
            if _is_model_decision(value):
                parsed = value
                break
        if parsed is not None:
            break

    if parsed is None:
        return ModelDecision(answer=raw.strip())

    answer = parsed.get("answer")
    if isinstance(answer, str):
        return ModelDecision(answer=answer.strip())

    tool_name = parsed.get("tool") or parsed.get("name")
    arguments = parsed.get("arguments", parsed.get("args", {}))
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {}
    if isinstance(tool_name, str) and isinstance(arguments, dict):
        return ModelDecision(tool_name=tool_name, arguments=arguments)

    return ModelDecision(answer=raw.strip())


class ExecuTorchRunner:
    """Invoke ExecuTorch's LLM runner once per generated completion."""

    def __init__(
        self,
        runner_bin: str,
        model_path: str,
        tokenizer_path: str,
        *,
        max_new_tokens: int = 512,
        temperature: float = 0.0,
        timeout: float = 300.0,
        cwd: str | None = None,
        runner_args: list[str] | None = None,
    ) -> None:
        self.runner_bin = runner_bin
        self.model_path = model_path
        self.tokenizer_path = tokenizer_path
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.cwd = cwd
        self.runner_args = list(runner_args or [])

    def build_command(
        self,
        prompt_path: str,
        *,
        max_new_tokens: int | None = None,
        temperature: float | None = None,
    ) -> list[str]:
        """Build the standard ExecuTorch ``llama_main`` command."""
        tokens = max_new_tokens if max_new_tokens and max_new_tokens > 0 else self.max_new_tokens
        sampling = self.temperature if temperature is None else temperature
        return [
            self.runner_bin,
            *self.runner_args,
            "--model_path",
            self.model_path,
            "--tokenizer_path",
            self.tokenizer_path,
            "--prompt_file",
            prompt_path,
            "--max_new_tokens",
            str(tokens),
            "--temperature",
            str(sampling),
        ]

    def generate(
        self,
        prompt: str,
        *,
        max_new_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        prompt_path = ""
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".txt",
                encoding="utf-8",
                delete=False,
            ) as prompt_file:
                prompt_file.write(prompt)
                prompt_path = prompt_file.name
            proc = subprocess.run(
                self.build_command(
                    prompt_path,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                ),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.cwd,
            )
        finally:
            if prompt_path:
                Path(prompt_path).unlink(missing_ok=True)
        if proc.returncode != 0:
            raise RuntimeError(
                f"ExecuTorch runner exited {proc.returncode}: {proc.stderr.strip()[:500]}"
            )
        return proc.stdout.strip()


def _chat_message(decision: ModelDecision) -> tuple[dict[str, Any], str]:
    if decision.is_tool_call:
        tool_call_id = f"call_{uuid.uuid4().hex[:16]}"
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": tool_call_id,
                "type": "function",
                "function": {
                    "name": decision.tool_name,
                    "arguments": json.dumps(decision.arguments or {}, separators=(",", ":")),
                },
            }],
        }
        return message, "tool_calls"
    return {"role": "assistant", "content": decision.answer or ""}, "stop"


def _completion(model_id: str, decision: ModelDecision) -> dict[str, Any]:
    message, finish_reason = _chat_message(decision)
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_id,
        "choices": [{
            "index": 0,
            "message": message,
            "finish_reason": finish_reason,
        }],
    }


def _stream_events(model_id: str, decision: ModelDecision) -> list[dict[str, Any]]:
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())

    def chunk(delta: dict[str, Any], finish_reason: str | None = None) -> dict[str, Any]:
        return {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_id,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }

    events = [chunk({"role": "assistant"})]
    if decision.is_tool_call:
        events.append(chunk({
            "tool_calls": [{
                "index": 0,
                "id": f"call_{uuid.uuid4().hex[:16]}",
                "type": "function",
                "function": {
                    "name": decision.tool_name,
                    "arguments": json.dumps(decision.arguments or {}, separators=(",", ":")),
                },
            }],
        }))
        events.append(chunk({}, "tool_calls"))
    else:
        events.append(chunk({"content": decision.answer or ""}))
        events.append(chunk({}, "stop"))
    return events


def _make_handler(runner: TextGenerator, model_id: str):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _send_json(self, code: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_stream(self, events: list[dict[str, Any]]) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            for event in events:
                self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            self.close_connection = True

        def do_GET(self) -> None:  # noqa: N802
            if self.path.rstrip("/") == "/v1/models":
                self._send_json(200, {
                    "object": "list",
                    "data": [{"id": model_id, "object": "model"}],
                })
            else:
                self._send_json(404, {"error": {"message": "not found"}})

        def do_POST(self) -> None:  # noqa: N802
            if self.path.rstrip("/") != "/v1/chat/completions":
                self._send_json(404, {"error": {"message": "not found"}})
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                request = json.loads(self.rfile.read(length) or b"{}")
                prompt = render_agent_prompt(
                    request.get("messages", []),
                    request.get("tools", []),
                )
                raw = runner.generate(
                    prompt,
                    max_new_tokens=request.get("max_tokens"),
                    temperature=request.get("temperature"),
                )
                decision = parse_model_decision(raw)
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {
                    "error": {"message": str(exc), "type": type(exc).__name__},
                })
                return

            if request.get("stream"):
                self._send_stream(_stream_events(model_id, decision))
            else:
                self._send_json(200, _completion(model_id, decision))

        def log_message(self, *_: Any) -> None:
            return

    return Handler


def build_server(
    host: str,
    port: int,
    runner: TextGenerator,
    *,
    model_id: str,
) -> ThreadingHTTPServer:
    """Create, but do not start, the local ExecuTorch HTTP server."""
    return ThreadingHTTPServer((host, port), _make_handler(runner, model_id))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aura-executorch-server",
        description="OpenAI-compatible agent shim over an ExecuTorch LLM runner.",
    )
    parser.add_argument(
        "--backend",
        choices=["runner", "pipe-host"],
        default=os.environ.get("AURA_LLM_BACKEND", "runner"),
        help="'runner' reloads llama_main per call (default); 'pipe-host' keeps "
             "qnn_llm_host.exe warm and serves over a named pipe",
    )
    parser.add_argument("--model-path",
                        default=os.environ.get("AURA_MODEL_PATH"),
                        help="Gemma .pte model path (or AURA_MODEL_PATH)")
    parser.add_argument("--tokenizer-path",
                        default=os.environ.get("AURA_TOKENIZER_PATH"),
                        help="tokenizer model path (or AURA_TOKENIZER_PATH)")
    parser.add_argument("--model", default=os.environ.get(
        "AURA_EXECUTORCH_MODEL", "gemma-4-e2b-executorch"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8082)
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--cwd", default=None)

    # --- runner backend (reload-per-call) ---
    parser.add_argument("--runner-bin", help="[runner] path to ExecuTorch llama_main")
    parser.add_argument("--runner-arg", action="append", default=[],
                        help="[runner] argument inserted after the runner binary; repeatable")

    # --- pipe-host backend (persistent warm host) ---
    parser.add_argument("--host-bin", default=os.environ.get("AURA_HOST_BIN", "./bin/qnn_llm_host.exe"),
                        help="[pipe-host] path to qnn_llm_host.exe (default ./bin/)")
    parser.add_argument("--pipe-name", default=os.environ.get("AURA_PIPE_NAME", "gemma4"),
                        help="[pipe-host] named pipe to serve on")
    parser.add_argument("--decoder-model-version",
                        default=os.environ.get("AURA_DECODER_MODEL_VERSION", "gemma4"),
                        help="[pipe-host] decoder family for prompt templating")
    parser.add_argument("--seq-len-ceiling", type=int,
                        default=int(os.environ.get("AURA_SEQ_LEN_CEILING", "3800")),
                        help="[pipe-host] respawn the host before this position is reached")
    parser.add_argument("--qnn-sdk-root", default=os.environ.get("AURA_QNN_SDK_ROOT", ""),
                        help="[pipe-host] extracted QAIRT SDK root")
    parser.add_argument("--backend-dir",
                        default=os.environ.get("AURA_QNN_BACKEND_DIR", "./bin/RelWithDebInfo"),
                        help="[pipe-host] dir holding qnn_executorch_backend.dll (default ./bin/)")
    parser.add_argument("--hexagon-arch", default=os.environ.get("AURA_HEXAGON_ARCH", "73"),
                        help="[pipe-host] HTP arch, e.g. 73 for SC8380XP")
    args = parser.parse_args(argv)

    if not args.model_path or not args.tokenizer_path:
        parser.error("--model-path and --tokenizer-path are required "
                     "(or set AURA_MODEL_PATH / AURA_TOKENIZER_PATH)")

    runner: TextGenerator
    if args.backend == "pipe-host":
        if not args.host_bin:
            parser.error("--host-bin is required when --backend pipe-host")
        runner = PipeHostManager(
            args.host_bin,
            args.model_path,
            args.tokenizer_path,
            decoder_model_version=args.decoder_model_version,
            pipe_name=args.pipe_name,
            seq_len_ceiling=args.seq_len_ceiling,
            backend_dir=args.backend_dir,
            qnn_sdk_root=args.qnn_sdk_root,
            hexagon_arch=args.hexagon_arch,
            temperature=args.temperature,
            cwd=args.cwd,
        )
    else:
        if not args.runner_bin:
            parser.error("--runner-bin is required when --backend runner")
        runner = ExecuTorchRunner(
            args.runner_bin,
            args.model_path,
            args.tokenizer_path,
            max_new_tokens=args.max_new_tokens,
            temperature=args.temperature,
            timeout=args.timeout,
            cwd=args.cwd,
            runner_args=args.runner_arg,
        )

    server = build_server(args.host, args.port, runner, model_id=args.model)
    print(
        f"AURA ExecuTorch server on http://{args.host}:{args.port} "
        f"(model={args.model}, backend={args.backend})"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if isinstance(runner, PipeHostManager):
            runner.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
