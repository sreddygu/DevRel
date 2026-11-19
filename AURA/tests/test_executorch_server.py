"""Tests for the ExecuTorch OpenAI-compatible agent shim."""

from __future__ import annotations

import json
import sys
import threading
from http.client import HTTPConnection

from aura.agent.executorch_server import (
    ExecuTorchRunner,
    build_server,
    parse_model_decision,
    render_agent_prompt,
)


def test_render_agent_prompt_includes_tools_and_tool_results() -> None:
    prompt = render_agent_prompt(
        [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "What machine is this?"},
            {"role": "tool", "tool_call_id": "call_1", "content": "edge-host"},
        ],
        [{
            "type": "function",
            "function": {
                "name": "run_command",
                "description": "Run one safe command.",
                "parameters": {"type": "object"},
            },
        }],
    )
    assert '"name":"run_command"' in prompt
    assert "TOOL_RESULT[call_1]: edge-host" in prompt
    assert prompt.endswith("ASSISTANT:")


def test_parse_model_decision_reads_answer_marker() -> None:
    result = parse_model_decision(
        'runner logs\n<AURA_RESPONSE>{"answer":"Ready."}</AURA_RESPONSE>'
    )
    assert result.answer == "Ready."
    assert not result.is_tool_call


def test_parse_model_decision_reads_tool_call() -> None:
    result = parse_model_decision(
        '<AURA_RESPONSE>{"tool":"run_command",'
        '"arguments":{"command":"hostname"}}</AURA_RESPONSE>'
    )
    assert result.tool_name == "run_command"
    assert result.arguments == {"command": "hostname"}


def test_parse_model_decision_ignores_nested_argument_objects() -> None:
    result = parse_model_decision(
        'runner stats: {"tokens":42}\n'
        '{"tool":"run_command","arguments":{"command":"pwd"}}\n'
        'generation complete'
    )
    assert result.tool_name == "run_command"
    assert result.arguments == {"command": "pwd"}


def test_runner_uses_prompt_file_and_standard_executorch_flags(tmp_path) -> None:
    script = tmp_path / "fake_runner.py"
    script.write_text(
        """
import pathlib
import sys

args = sys.argv[1:]
prompt_path = args[args.index('--prompt_file') + 1]
assert 'ASSISTANT:' in pathlib.Path(prompt_path).read_text(encoding='utf-8')
print('<AURA_RESPONSE>{"answer":"runner ok"}</AURA_RESPONSE>')
""",
        encoding="utf-8",
    )
    runner = ExecuTorchRunner(
        sys.executable,
        "gemma.pte",
        "tokenizer.model",
        runner_args=[str(script)],
    )
    output = runner.generate("USER: hello\nASSISTANT:", max_new_tokens=64, temperature=0.1)
    assert "runner ok" in output


class _FakeRunner:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.prompt = ""

    def generate(self, prompt: str, **_: object) -> str:
        self.prompt = prompt
        return self.reply


def _serve(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


def _post(port: int, payload: dict) -> tuple[int, str, str]:
    conn = HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request(
        "POST",
        "/v1/chat/completions",
        body=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
    response = conn.getresponse()
    body = response.read().decode()
    content_type = response.getheader("Content-Type", "")
    conn.close()
    return response.status, content_type, body


def test_non_streaming_tool_call_response() -> None:
    runner = _FakeRunner(
        '<AURA_RESPONSE>{"tool":"run_command",'
        '"arguments":{"command":"hostname"}}</AURA_RESPONSE>'
    )
    server = build_server("127.0.0.1", 0, runner, model_id="gemma-4-e2b-executorch")
    _serve(server)
    try:
        status, _, body = _post(server.server_address[1], {
            "messages": [{"role": "user", "content": "Run hostname"}],
            "tools": [{
                "type": "function",
                "function": {"name": "run_command", "parameters": {"type": "object"}},
            }],
        })
    finally:
        server.shutdown()
        server.server_close()

    data = json.loads(body)
    message = data["choices"][0]["message"]
    assert status == 200
    assert data["choices"][0]["finish_reason"] == "tool_calls"
    assert message["tool_calls"][0]["function"]["name"] == "run_command"
    assert json.loads(message["tool_calls"][0]["function"]["arguments"]) == {
        "command": "hostname"
    }
    assert "Available tools:" in runner.prompt


def test_streaming_answer_uses_openai_sse_shape() -> None:
    runner = _FakeRunner('<AURA_RESPONSE>{"answer":"hello"}</AURA_RESPONSE>')
    server = build_server("127.0.0.1", 0, runner, model_id="gemma-4-e2b-executorch")
    _serve(server)
    try:
        status, content_type, body = _post(server.server_address[1], {
            "messages": [{"role": "user", "content": "Say hello"}],
            "stream": True,
        })
    finally:
        server.shutdown()
        server.server_close()

    assert status == 200
    assert content_type.startswith("text/event-stream")
    assert '"content": "hello"' in body
    assert '"finish_reason": "stop"' in body
    assert body.rstrip().endswith("data: [DONE]")
