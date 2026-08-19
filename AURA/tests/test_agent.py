# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""Tests for the Brain milestone (Milestone 4): LocalLLM + AuraPipeline.ask.

The LLM HTTP calls are exercised against an httpx MockTransport, so no live
llama-server is required. These tests need the ``agent`` extra (httpx); they
skip cleanly if it isn't installed, keeping the base-install suite green.
"""

from __future__ import annotations

import json

import pytest

httpx = pytest.importorskip("httpx")  # agent extra

from aura.agent.llm import LocalLLM  # noqa: E402
from aura.core.events import Event  # noqa: E402
from aura.core.pipeline import AuraPipeline  # noqa: E402


def _mock_llm(capture: dict | None = None, reply: str = "ok") -> LocalLLM:
    """A LocalLLM whose endpoint echoes a canned reply and records the request."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if capture is not None:
            capture["path"] = request.url.path
            capture["model"] = body["model"]
            capture["messages"] = body["messages"]
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": reply}}]}
        )

    return LocalLLM(model="test-model", transport=httpx.MockTransport(handler))


def _mock_llm_no_think(capture: dict, reply: str = "ok") -> LocalLLM:
    """Like ``_mock_llm`` but with ``no_think`` enabled."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        capture["messages"] = body["messages"]
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": reply}}]}
        )

    return LocalLLM(model="test-model", no_think=True, transport=httpx.MockTransport(handler))


def test_chat_posts_to_openai_path_and_returns_content() -> None:
    cap: dict = {}
    llm = _mock_llm(cap, reply="hello there")
    out = llm.chat([{"role": "user", "content": "hi"}])
    assert out == "hello there"
    assert cap["path"] == "/v1/chat/completions"
    assert cap["model"] == "test-model"


def test_summarize_builds_prompt_from_events() -> None:
    cap: dict = {}
    llm = _mock_llm(cap, reply="A person and a package were seen.")
    events = [Event(event="person entered room"), Event(event="package delivered")]
    out = llm.summarize(events)
    assert out == "A person and a package were seen."
    user_msg = cap["messages"][-1]["content"]
    assert "person entered room" in user_msg
    assert "package delivered" in user_msg


def test_summarize_empty_events_short_circuits() -> None:
    # No HTTP call should be needed; transport would error if hit.
    llm = LocalLLM(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    assert llm.summarize([]) == "No events were recorded."


def test_answer_includes_question_and_context() -> None:
    cap: dict = {}
    llm = _mock_llm(cap, reply="On the front table.")
    ctx = [Event(event="package left on front table", location="hall")]
    out = llm.answer("Where is the package?", ctx)
    assert out == "On the front table."
    user_msg = cap["messages"][-1]["content"]
    assert "Where is the package?" in user_msg
    assert "front table" in user_msg


class _FakeMemory:
    """Minimal stand-in exposing the recall() surface ask() depends on."""

    def __init__(self, events: list[Event]) -> None:
        self._events = events
        self.recall_arg: str | None = None

    def recall(self, text: str, *, k: int = 5) -> list[Event]:
        self.recall_arg = text
        return self._events


def test_pipeline_ask_grounds_answer_in_recalled_events() -> None:
    cap: dict = {}
    events = [Event(event="laptop detected", location="kitchen", entities=["laptop"])]
    pipe = AuraPipeline(memory=_FakeMemory(events), llm=_mock_llm(cap, reply="In the kitchen."))
    out = pipe.ask("Where is my laptop?")
    assert out == "In the kitchen."
    # the question drove recall, and the recalled event reached the LLM
    assert "kitchen" in cap["messages"][-1]["content"]


def test_pipeline_ask_requires_memory_and_llm() -> None:
    with pytest.raises(RuntimeError):
        AuraPipeline().ask("anything?")


def test_chat_strips_think_block_from_reply() -> None:
    llm = _mock_llm(reply="<think>reasoning noise\nmore</think>\n\nThe answer is 42.")
    assert llm.chat([{"role": "user", "content": "q"}]) == "The answer is 42."


def test_chat_strips_empty_think_block() -> None:
    # /no_think makes Qwen3 emit an empty block rather than none.
    llm = _mock_llm(reply="<think>\n\n</think>\n\nDone.")
    assert llm.chat([{"role": "user", "content": "q"}]) == "Done."


def test_no_think_appends_switch_to_last_user_message() -> None:
    cap: dict = {}
    llm = _mock_llm_no_think(cap, reply="ok")
    llm.chat([
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "Where is it?"},
    ])
    assert cap["messages"][-1]["content"] == "Where is it? /no_think"
    # system message is untouched
    assert cap["messages"][0]["content"] == "sys"


def test_no_think_disabled_by_default_leaves_prompt_intact() -> None:
    cap: dict = {}
    llm = _mock_llm(cap, reply="ok")
    llm.chat([{"role": "user", "content": "hi"}])
    assert cap["messages"][-1]["content"] == "hi"
