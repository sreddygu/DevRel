"""Milestone 5 demo — Action.

Shows AURA selecting and invoking tools in response to a natural-language
command, then remembering the action alongside earlier perception events.

Usage (with a live local LLM server):

    # Start llama-server (or GenieX) first, then:
    python examples/act_demo.py

The demo runs hardware-free by default (MockSmartHomeTransport). To target a
real smart-home adapter, swap in your own SmartHomeTransport implementation.

Environment variables (all optional):
    AURA_LLM_BASE_URL   LLM endpoint (default: http://127.0.0.1:8080)
    AURA_LLM_MODEL      Model id      (default: gemma-2-2b-it)
    AURA_NO_THINK       Set to "true" to strip Qwen3 <think> blocks
"""

from __future__ import annotations

import os

from aura.agent.llm import LocalLLM
from aura.agent.tools import MockSmartHomeTransport, default_tools
from aura.core.events import Event
from aura.core.pipeline import AuraPipeline
from aura.memory.store import MemoryStore

# ── Build the pipeline ────────────────────────────────────────────────────────
store = MemoryStore(":memory:")

# Seed some perception context so the LLM has something to reason over.
store.add_event(Event(event="workshop light is on", type="detection", source="vision", location="workshop"))
store.add_event(Event(event="package delivered at front door", type="detection", source="vision", location="front door"))

transport = MockSmartHomeTransport()
tools = default_tools(smart_home=transport)

base_url = os.getenv("AURA_LLM_BASE_URL", "http://127.0.0.1:8080")
model    = os.getenv("AURA_LLM_MODEL",    "gemma-2-2b-it")
no_think = os.getenv("AURA_NO_THINK", "").lower() in {"1", "true", "yes"}

llm = LocalLLM(base_url=base_url, model=model, no_think=no_think)

pipe = AuraPipeline(memory=store, llm=llm, tools=tools)

# ── Run a command ─────────────────────────────────────────────────────────────
command = "Turn on the workshop lights and activate the movie night scene."
print(f"\nCommand: {command}\n")

answer, action_events = pipe.act(command)

print(f"AURA: {answer}\n")
print(f"Actions taken ({len(action_events)}):")
for ev in action_events:
    print(f"  {ev.event}  (args: {ev.attributes.get('args', {})})")

print(f"\nTransport calls recorded: {transport.calls}")

# ── Show that actions are persisted in memory ─────────────────────────────────
print("\nAll events in memory (chronological):")
for ev in store.query():
    print(f"  [{ev.type}] {ev.event}")
