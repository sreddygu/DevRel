# Author: Srinivas Reddy Gudala
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

import re
from typing import Any

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
    "question using ONLY the observed events provided as context. If the "
    "events don't contain the answer, say you don't have a record of it."
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
    """Render Events (or dicts) as a compact, one-per-line context block."""
    return "\n".join(f"- {ev}" for ev in events)


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
