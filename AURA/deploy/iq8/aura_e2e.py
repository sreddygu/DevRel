#!/usr/bin/env python3
# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""AURA full on-device loop on the IQ8: perceive -> remember -> reason -> act.

Wheel-free (stdlib + numpy/cv2 only), mirroring the other deploy/iq8 drivers.
Each stage runs on the device it belongs on:

  * perceive : vision on the Hexagon NPU (aura_npu_detect) + speech STT (whisper)
  * remember : AURA MemoryStore (SQLite, from the installed package)
  * reason   : local LLM over HTTP (llama-server, OpenAI-compatible) via urllib
  * act      : a simple actuator tool that logs an action Event back to memory

The LLM step talks to llama-server with stdlib urllib (no httpx on-device).
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, "/opt/aura/src")
sys.path.insert(0, "/opt/aura-vision")
sys.path.insert(0, "/opt/aura-speech")

from aura.core.events import Event  # noqa: E402
from aura.memory.store import MemoryStore  # noqa: E402

LLM_URL = os.environ.get("AURA_LLM_BASE_URL", "http://127.0.0.1:8080")
LLM_MODEL = os.environ.get("AURA_LLM_MODEL", "qwen2.5-0.5b")
DB = "/opt/aura/aura_e2e.db"
IMG = os.environ.get("AURA_IMG", "/opt/aura-vision/data/bus.jpg")
WAV = os.environ.get("AURA_WAV", "/opt/aura-speech/jfk.wav")


def llm_chat(system, user, max_tokens=200):
    """OpenAI-compatible chat completion over stdlib urllib."""
    body = json.dumps({
        "model": LLM_MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(LLM_URL + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.load(r)
    return out["choices"][0]["message"]["content"].strip()


def main():
    print("=" * 60)
    print("AURA end-to-end on IQ8 (perceive -> remember -> reason -> act)")
    print("=" * 60)

    store = MemoryStore(DB).connect()

    # ---- 1. PERCEIVE: vision on NPU ------------------------------------
    print("\n[1/4 PERCEIVE] vision on Hexagon NPU ...")
    import aura_npu_detect as vision
    vevents = vision.detect(IMG, location="living room")
    counts = {}
    for e in vevents:
        counts[e["entities"][0]] = counts.get(e["entities"][0], 0) + 1
    print("  scene:", ", ".join("%d %s" % (n, l) for l, n in counts.items()))
    for e in vevents:
        store.add_event(Event(event=e["event"], type="detection", source="vision",
                              entities=e["entities"], location=e["location"],
                              confidence=e["confidence"]))

    # ---- 1b. PERCEIVE: speech STT (CPU) --------------------------------
    print("\n[1/4 PERCEIVE] speech STT (whisper.cpp, CPU) ...")
    import aura_stt as stt
    spoken = stt.transcribe(WAV)
    print("  heard:", spoken[:70] + ("..." if len(spoken) > 70 else ""))
    store.add_event(Event(event=spoken, type="speech", source="speech"))

    # ---- 2. REMEMBER ---------------------------------------------------
    print("\n[2/4 REMEMBER] events persisted to SQLite ...")
    all_events = store.query()
    print("  %d events in memory; where_is('bus') ->" % len(all_events),
          (store.where_is("bus").location if store.where_is("bus") else None))

    # ---- 3. REASON: local LLM over remembered events -------------------
    print("\n[3/4 REASON] local LLM (llama-server, CPU) grounded answer ...")
    context = "\n".join("- %s (%s)" % (e.event, e.location or "?")
                        for e in all_events if e.type == "detection")
    question = "What did you see, and how many people are in view?"
    system = ("You are AURA, a privacy-first physical-AI agent. Answer using ONLY "
              "the observed events provided. Be concise.")
    answer = llm_chat(system, "Observed events:\n%s\n\nQuestion: %s" % (context, question))
    print("  Q:", question)
    print("  A:", answer)

    # ---- 4. ACT: decide + actuate (logged back to memory) --------------
    print("\n[4/4 ACT] actuator tool -> action Event ...")
    people = counts.get("person", 0)
    action = "set_light(porch, ON)" if people > 0 else "set_light(porch, OFF)"
    result = "porch light ON — %d person(s) detected" % people
    store.add_event(Event(event="%s: %s" % (action, result), type="action",
                          source="agent", entities=["light"], location="porch"))
    print("  decided:", action, "->", result)

    print("\n" + "=" * 60)
    print("LOOP COMPLETE — action Events now in memory:")
    for e in store.query(type="action"):
        print("  •", e.event)
    store.close()
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(main())
