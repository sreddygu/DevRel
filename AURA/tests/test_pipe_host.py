"""Tests for the warm named-pipe ExecuTorch backend (``aura.agent.pipe_host``).

No real ``qnn_llm_host.exe`` and no NPU: a fake spawner injects a fake client so
the manager's lifecycle, budget-guard, and error handling are exercised in pure
Python, and the result is run through the unchanged shim parser.
"""

from __future__ import annotations

import os

from aura.agent.executorch_server import parse_model_decision
from aura.agent.pipe_host import PipeHostManager, build_host_env


class _FakeClient:
    """Stand-in for PipeHostClient: canned replies, records what it saw."""

    def __init__(self, replies: list[dict]) -> None:
        self._replies = list(replies)
        self.requests: list[dict] = []
        self.shutdown_calls = 0

    def request(self, payload: dict) -> dict:
        self.requests.append(payload)
        if payload.get("cmd") == "shutdown":
            return {"ok": True}
        return self._replies.pop(0)

    def shutdown(self) -> None:
        self.shutdown_calls += 1

    def close(self) -> None:
        pass


class _FakeProc:
    def __init__(self) -> None:
        self.terminated = False

    def poll(self):  # still running
        return None

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout=None) -> int:
        return 0

    def kill(self) -> None:
        self.terminated = True


def _manager_with(replies, **kwargs) -> tuple[PipeHostManager, dict]:
    """Build a manager whose spawner hands back a shared fake client."""
    state: dict = {"spawns": 0, "clients": []}

    def spawner(_manager):
        state["spawns"] += 1
        client = _FakeClient(replies)
        state["clients"].append(client)
        return _FakeProc(), client

    manager = PipeHostManager(
        "qnn_llm_host.exe",
        "gemma.pte",
        "tokenizer.json",
        spawner=spawner,
        **kwargs,
    )
    return manager, state


def test_build_host_env_sets_the_three_qnn_vars() -> None:
    env = build_host_env(
        r"C:\Qualcomm\AIStack\QAIRT\2.47.1.260610",
        r"C:\proj\AURA\bin\RelWithDebInfo",
        hexagon_arch=73,
        base_env={"Path": r"C:\existing"},
    )
    assert env["QNN_SDK_ROOT"] == r"C:\Qualcomm\AIStack\QAIRT\2.47.1.260610"
    assert env["ADSP_LIBRARY_PATH"].endswith(
        os.path.join("lib", "hexagon-v73", "unsigned")
    )
    # Backend dir and the aarch64 lib dir are both prepended, existing Path kept.
    assert env["Path"].startswith(r"C:\proj\AURA\bin\RelWithDebInfo")
    assert "aarch64-windows-msvc" in env["Path"]
    assert env["Path"].endswith(r"C:\existing")


def test_generate_returns_text_and_feeds_the_prompt() -> None:
    manager, state = _manager_with([
        {"ok": True, "text": '<AURA_RESPONSE>{"answer":"Ready."}</AURA_RESPONSE>'},
    ])
    raw = manager.generate("USER: hi\nASSISTANT:", max_new_tokens=64)
    assert state["spawns"] == 1
    sent = state["clients"][0].requests[0]
    assert sent["prompt"].endswith("ASSISTANT:")
    # The unchanged shim parser still extracts the decision.
    assert parse_model_decision(raw).answer == "Ready."


def test_generate_parses_a_tool_call_through_the_shim() -> None:
    manager, _ = _manager_with([
        {"ok": True, "text": '<AURA_RESPONSE>{"tool":"move_robot",'
                             '"arguments":{"direction":"forward"}}</AURA_RESPONSE>'},
    ])
    decision = parse_model_decision(manager.generate("go"))
    assert decision.tool_name == "move_robot"
    assert decision.arguments == {"direction": "forward"}


def test_error_response_raises() -> None:
    manager, _ = _manager_with([{"ok": False, "error": "sequence length exceeded"}])
    try:
        manager.generate("boom")
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "sequence length exceeded" in str(exc)


def test_budget_guard_respawns_before_ceiling() -> None:
    # Tiny ceiling so the second call's projection crosses it and forces a reset.
    manager, state = _manager_with(
        [
            {"ok": True, "text": "x" * 400},   # first turn advances the position
            {"ok": True, "text": "ok"},        # second turn should hit a respawn
        ],
        seq_len_ceiling=120,
        chars_per_token=4.0,
    )
    manager.generate("first turn prompt")
    assert state["spawns"] == 1
    manager.generate("second turn prompt")
    # Crossing the ceiling killed + relaunched the host to reset the KV-cache.
    assert state["spawns"] == 2


def test_close_shuts_down_and_terminates() -> None:
    manager, state = _manager_with([{"ok": True, "text": "hi"}])
    manager.generate("hello")
    proc = manager._proc
    client = state["clients"][0]
    manager.close()
    assert client.shutdown_calls == 1
    assert proc.terminated
    assert manager._proc is None
