# Author: Srinivas Reddy Gudala
# Email: sreddygu@qti.qualcomm.com
# Last Updated: 2026-08-17
# Version: 1.0
#
"""Local LLM client (Milestone 4, "Brain").

Talks to an on-device, OpenAI-compatible LLM server (llama.cpp ``llama-server``
or a Genie NPU server) over HTTP — keeping all reasoning local, no cloud.
``httpx`` is imported lazily inside the request methods (``agent`` extra).

Used to summarize the day, answer questions grounded in remembered Events, and
(with :mod:`aura.agent.tools`) decide which actions to take.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aura.agent.tools import Tool

# Qwen3 (and other reasoning models) wrap their chain-of-thought in
# ``<think>…</think>`` before the actual answer. We strip it so callers get a
# clean response. The ``/no_think`` soft switch (see ``no_think`` below) makes
# the model emit an *empty* block rather than none, so we strip either way.
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

# System prompts kept module-level so they're easy to review and tune.
_SUMMARY_SYSTEM = (
    "You are AURA, a privacy-first physical-AI agent. Summarize the day's "
    "observed events into a short, factual narrative. Only use the events "
    "given; do not invent details."
)
_ANSWER_SYSTEM = (
    "You are AURA, a privacy-first physical-AI agent. Answer the user's "
    "question using ONLY the Events and Knowledge sources provided as context. "
    "If the context does not contain the answer, say you don't have a record "
    "of it. When using a Knowledge source, include its source filename."
)


class LocalLLM:
    """Client for a local OpenAI-compatible chat endpoint.

    Args:
        base_url: e.g. ``http://127.0.0.1:8080`` (llama.cpp ``/v1`` server).
        model: Model id to request, e.g. ``"gemma-2-2b-it"`` or a Qwen build.
        timeout: Per-request timeout in seconds. Defaults high (300s) because
            the Genie NPU shim reloads the model per request — a cold call can
            take a minute or more before the first token.
        no_think: When True, append ``/no_think`` to the prompt — the Qwen3
            soft switch that disables reasoning mode. HTTP-level flags
            (``think``/``chat_template_kwargs``) are not honored by the GenieX
            server, so the prompt-level switch is the reliable lever. Regardless
            of this flag, any ``<think>…</think>`` block is stripped from the
            reply.
        transport: Optional httpx transport (used by tests to inject a mock);
            ``None`` uses the default network transport.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080",
        *,
        model: str = "gemma-2-2b-it",
        timeout: float = 300.0,
        no_think: bool = False,
        transport: Any = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.no_think = no_think
        self._transport = transport

    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """Send a chat completion request; return the assistant text.

        POSTs to ``{base_url}/v1/chat/completions``. Extra kwargs (e.g.
        ``temperature``, ``max_tokens``) are forwarded to the server. When
        ``no_think`` is set, ``/no_think`` is appended to the last user message.
        Any ``<think>…</think>`` reasoning block is stripped from the reply.
        """
        import httpx  # noqa: PLC0415  (lazy: only when the LLM is actually used)

        if self.no_think:
            messages = _append_no_think(messages)
        payload = {"model": self.model, "messages": messages, **kwargs}
        with httpx.Client(timeout=self.timeout, transport=self._transport) as client:
            resp = client.post(f"{self.base_url}/v1/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
        return _strip_think(data["choices"][0]["message"]["content"])

    def summarize(self, events: list[Any]) -> str:
        """Summarize a list of Events into a short narrative.

        Powers "Summarize today's events." — builds a prompt from the Events
        and calls :meth:`chat`.
        """
        if not events:
            return "No events were recorded."
        messages = [
            {"role": "system", "content": _SUMMARY_SYSTEM},
            {"role": "user", "content": "Events:\n" + _format_events(events)},
        ]
        return self.chat(messages)

    def act(
        self,
        command: str,
        tools: list[Tool],
        context: list[Any] | None = None,
        *,
        max_rounds: int = 5,
    ) -> tuple[str, list[Any]]:
        """Execute a voice/text command by selecting and invoking tools.

        Sends *command* (and optionally grounding *context* events) to the LLM
        together with the tool specs. The LLM either calls a tool (which is
        executed locally and fed back as a ``tool`` message) or produces a final
        text answer. Loops up to *max_rounds* tool calls, then returns.

        Returns:
            A ``(final_answer, action_events)`` tuple — the LLM's final text
            reply and a list of ``action`` :class:`~aura.core.events.Event`
            objects produced by each tool invocation.
        """
        import httpx  # noqa: PLC0415

        tool_map = {t.name: t for t in tools}
        tool_specs = [t.to_openai_spec() for t in tools]

        system_content = (
            "You are AURA, a privacy-first physical-AI agent. "
            "Use the available tools to carry out the user's command. "
            "Only use the tools provided; do not invent tool names."
        )
        if context:
            system_content += "\n\nRecent observations:\n" + _format_events(context)

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": command},
        ]
        if self.no_think:
            messages = _append_no_think(messages)

        action_events: list[Any] = []

        for _ in range(max_rounds):
            payload: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "tools": tool_specs,
                "tool_choice": "auto",
            }
            with httpx.Client(timeout=self.timeout, transport=self._transport) as client:
                resp = client.post(f"{self.base_url}/v1/chat/completions", json=payload)
                resp.raise_for_status()
                data = resp.json()

            choice = data["choices"][0]
            assistant_msg = choice["message"]
            finish = choice.get("finish_reason", "stop")
            messages.append(assistant_msg)

            if finish != "tool_calls" or not assistant_msg.get("tool_calls"):
                # LLM is done — return its text answer.
                content = assistant_msg.get("content") or ""
                return _strip_think(content), action_events

            # Execute each tool call and feed results back.
            for tc in assistant_msg["tool_calls"]:
                fn = tc["function"]
                name = fn["name"]
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}

                if name not in tool_map:
                    result_text = f"Error: unknown tool '{name}'"
                    tool_event = None
                else:
                    tool_event = tool_map[name].invoke(**args)
                    result_text = tool_event.event
                    action_events.append(tool_event)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", name),
                    "content": result_text,
                })

        # Exhausted rounds — return last assistant content if any.
        for m in reversed(messages):
            if m.get("role") == "assistant" and m.get("content"):
                return _strip_think(m["content"]), action_events
        return "", action_events

    def answer(self, question: str, context: list[Any]) -> str:
        """Answer ``question`` grounded in ``context`` Events (RAG-style)."""
        context_block = _format_events(context) if context else "(no relevant events)"
        messages = [
            {"role": "system", "content": _ANSWER_SYSTEM},
            {
                "role": "user",
                "content": f"Observed events:\n{context_block}\n\nQuestion: {question}",
            },
        ]
        return self.chat(messages)


def _format_events(events: list[Any]) -> str:
    """Render Events and documentation chunks as grounded context."""
    lines = []
    for item in events:
        if isinstance(item, dict) and "text" in item:
            lines.append(f"- [{item.get('source', 'knowledge')}] {item['text']}")
        else:
            lines.append(f"- {item}")
    return "\n".join(lines)


def _strip_think(text: str) -> str:
    """Remove any ``<think>…</think>`` reasoning block and surrounding blank space."""
    return _THINK_RE.sub("", text).strip()


def _append_no_think(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """Return a copy of ``messages`` with ``/no_think`` appended to the last user turn.

    Falls back to appending a trailing user message if there isn't one (so the
    switch still reaches the model).
    """
    out = [dict(m) for m in messages]
    for m in reversed(out):
        if m.get("role") == "user":
            m["content"] = f"{m['content']} /no_think"
            return out
    out.append({"role": "user", "content": "/no_think"})
    return out
