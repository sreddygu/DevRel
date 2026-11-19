"""Tests for Milestone 5 (Action): SmartHomeTransport, Tool.to_openai_spec,
LocalLLM.act, and AuraPipeline.act.

All HTTP calls are intercepted by httpx.MockTransport — no live server needed.
"""

from __future__ import annotations

import json

import pytest

httpx = pytest.importorskip("httpx")  # agent extra

from aura.agent.llm import LocalLLM  # noqa: E402
from aura.agent.tools import (  # noqa: E402
    MockSmartHomeTransport,
    Tool,
    default_tools,
    smart_home_tools,
)
from aura.core.events import Event  # noqa: E402
from aura.core.pipeline import AuraPipeline  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────

def _llm_final(reply: str) -> LocalLLM:
    """LLM that always returns a plain text answer (no tool call)."""
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": reply, "tool_calls": []},
            }]
        })
    return LocalLLM(model="test", transport=httpx.MockTransport(handler))


def _llm_calls_tool(tool_name: str, args: dict, final_reply: str) -> LocalLLM:
    """LLM that calls one tool then returns a final answer."""
    call_count = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, json={
                "choices": [{
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": "tc1",
                            "type": "function",
                            "function": {"name": tool_name, "arguments": json.dumps(args)},
                        }],
                    },
                }]
            })
        return httpx.Response(200, json={
            "choices": [{
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": final_reply, "tool_calls": []},
            }]
        })

    return LocalLLM(model="test", transport=httpx.MockTransport(handler))


# ── SmartHomeTransport ────────────────────────────────────────────────────────

def test_mock_transport_records_set_light() -> None:
    t = MockSmartHomeTransport()
    result = t.set_light("workshop", "on")
    assert "workshop" in result
    assert t.calls == [("set_light", {"name": "workshop", "state": "on"})]


def test_mock_transport_records_run_scene() -> None:
    t = MockSmartHomeTransport()
    result = t.run_scene("movie night")
    assert "movie night" in result
    assert t.calls == [("run_scene", {"name": "movie night"})]


# ── Tool.to_openai_spec ───────────────────────────────────────────────────────

def test_tool_openai_spec_shape() -> None:
    tools = smart_home_tools(MockSmartHomeTransport())
    spec = tools[0].to_openai_spec()
    assert spec["type"] == "function"
    assert "name" in spec["function"]
    assert "parameters" in spec["function"]


def test_set_light_spec_has_required_fields() -> None:
    tool = next(t for t in smart_home_tools(MockSmartHomeTransport()) if t.name == "set_light")
    spec = tool.to_openai_spec()
    required = spec["function"]["parameters"]["required"]
    assert "name" in required
    assert "state" in required


# ── smart_home_tools invoke ───────────────────────────────────────────────────

def test_smart_home_set_light_invoke_returns_action_event() -> None:
    t = MockSmartHomeTransport()
    tools = smart_home_tools(t)
    set_light = next(tool for tool in tools if tool.name == "set_light")
    ev = set_light.invoke(name="workshop", state="on")
    assert ev.type == "action"
    assert "workshop" in ev.event
    assert t.calls == [("set_light", {"name": "workshop", "state": "on"})]


def test_smart_home_run_scene_invoke_returns_action_event() -> None:
    t = MockSmartHomeTransport()
    tools = smart_home_tools(t)
    run_scene = next(tool for tool in tools if tool.name == "run_scene")
    ev = run_scene.invoke(name="movie night")
    assert ev.type == "action"
    assert "movie night" in ev.event


# ── default_tools ─────────────────────────────────────────────────────────────

def test_default_tools_stub_raises_without_transport() -> None:
    set_light = next(t for t in default_tools() if t.name == "set_light")
    with pytest.raises(NotImplementedError):
        set_light.invoke(name="x", state="on")


def test_default_tools_live_with_transport() -> None:
    t = MockSmartHomeTransport()
    set_light = next(t2 for t2 in default_tools(smart_home=t) if t2.name == "set_light")
    ev = set_light.invoke(name="desk", state="off")
    assert ev.type == "action"


# ── LocalLLM.act ─────────────────────────────────────────────────────────────

def test_act_no_tool_call_returns_answer() -> None:
    llm = _llm_final("Done.")
    tools = smart_home_tools(MockSmartHomeTransport())
    answer, events = llm.act("dim everything", tools)
    assert answer == "Done."
    assert events == []


def test_act_single_tool_call_returns_event_and_answer() -> None:
    t = MockSmartHomeTransport()
    tools = smart_home_tools(t)
    llm = _llm_calls_tool("set_light", {"name": "workshop", "state": "on"}, "Workshop light is on.")
    answer, events = llm.act("turn on workshop light", tools)
    assert answer == "Workshop light is on."
    assert len(events) == 1
    assert events[0].type == "action"
    assert t.calls == [("set_light", {"name": "workshop", "state": "on"})]


def test_act_unknown_tool_name_does_not_crash() -> None:
    tools = smart_home_tools(MockSmartHomeTransport())
    llm = _llm_calls_tool("nonexistent_tool", {}, "Could not complete.")
    answer, events = llm.act("do something", tools)
    assert events == []  # unknown tool produces no event
    assert "Could not complete" in answer


def test_act_includes_context_in_system_prompt() -> None:
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.content)
        return httpx.Response(200, json={
            "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "ok", "tool_calls": []}}]
        })

    llm = LocalLLM(model="test", transport=httpx.MockTransport(handler))
    context = [Event(event="lights are off", location="workshop")]
    tools = smart_home_tools(MockSmartHomeTransport())
    llm.act("turn on workshop", tools, context)
    system_msg = captured["body"]["messages"][0]["content"]
    assert "lights are off" in system_msg


# ── AuraPipeline.act ──────────────────────────────────────────────────────────

class _FakeMemory:
    def __init__(self) -> None:
        self.stored: list[Event] = []
        self.recalled: list[Event] = []

    def recall(self, text: str, *, k: int = 5) -> list[Event]:
        return self.recalled

    def add_event(self, ev: Event) -> None:
        self.stored.append(ev)


def test_pipeline_act_invokes_tool_and_persists_event() -> None:
    t = MockSmartHomeTransport()
    tools = smart_home_tools(t)
    mem = _FakeMemory()
    llm = _llm_calls_tool("set_light", {"name": "hall", "state": "off"}, "Hall light off.")
    pipe = AuraPipeline(memory=mem, llm=llm, tools=tools)

    answer, events = pipe.act("turn off hall light")
    assert answer == "Hall light off."
    assert len(events) == 1
    assert events[0] in mem.stored  # action was persisted


def test_pipeline_act_requires_llm() -> None:
    pipe = AuraPipeline(tools=smart_home_tools(MockSmartHomeTransport()))
    with pytest.raises(RuntimeError, match="llm"):
        pipe.act("anything")


def test_pipeline_act_requires_tools() -> None:
    pipe = AuraPipeline(llm=_llm_final("ok"))
    with pytest.raises(RuntimeError, match="tool"):
        pipe.act("anything")


def test_pipeline_act_without_memory_still_works() -> None:
    t = MockSmartHomeTransport()
    tools = smart_home_tools(t)
    llm = _llm_calls_tool("run_scene", {"name": "sunrise"}, "Scene activated.")
    pipe = AuraPipeline(llm=llm, tools=tools)  # no memory
    answer, events = pipe.act("activate sunrise scene")
    assert "Scene activated" in answer
    assert len(events) == 1
