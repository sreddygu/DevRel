"""Answer a question from pulled context using any OpenAI-compatible endpoint.

The same call works against llama.cpp, Ollama or a Genie/GenieX server, which is
what makes the ``--base-url`` swap the cross-device orchestration step. The answer
is grounded: only the Events in the local store are put in the prompt.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from aura.memory.store import MemoryStore

SYSTEM = (
    "You answer questions about what happened using ONLY the numbered events provided. "
    "If the events do not contain the answer, say you do not know. Be brief."
)


def build_messages(question: str, store: MemoryStore, *, since: str | None = None, limit: int = 50) -> tuple[list[dict], int]:
    events = list(reversed(store.query(since=since, limit=limit)))  # oldest first
    lines = [f"{i}. {e}" for i, e in enumerate(events, 1)] or ["(no events)"]
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Events:\n" + "\n".join(lines) + f"\n\nQuestion: {question}"},
    ]
    return messages, len(events)


def ask(
    question: str,
    store: MemoryStore,
    *,
    base_url: str,
    model: str,
    since: str | None = None,
    api_key: str = "none",
    timeout: float = 120,
) -> dict:
    """Return ``{"answer": str, "model": str, "base_url": str, "events_used": int}``."""
    messages, used = build_messages(question, store, since=since)
    body = json.dumps({"model": model, "messages": messages, "temperature": 0, "stream": False}).encode()
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - caller-supplied endpoint
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"model endpoint returned HTTP {err.code}: {detail}") from err
    return {
        "answer": data["choices"][0]["message"]["content"].strip(),
        "model": data.get("model", model),
        "base_url": base_url,
        "events_used": used,
    }
