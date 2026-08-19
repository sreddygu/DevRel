#!/usr/bin/env python3
# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""AURA interactive live loop on the IQ8.

A conversational REPL that runs the full perceive->remember->reason->act loop
against LIVE data each turn:

  * HEAR   : record a few seconds from the live mic (ALSA arecord) -> whisper STT
  * SEE    : grab a live camera frame if one is available, else use a still image;
             run YOLOv8 on the Hexagon NPU
  * REMEMBER: persist perceptions to the AURA MemoryStore (SQLite)
  * REASON : answer your spoken question with the local LLM, grounded in memory
  * SPEAK  : synthesize the reply with piper and play it through the speakers

Controls (typed at the prompt):
    <Enter>       record a spoken question (default 5s) and run one full turn
    t <text>      ask a typed question instead of speaking
    look          just re-perceive the scene (camera/still) and report
    secs N        change mic record seconds
    q             quit

Wheel-free: stdlib + numpy/cv2 only. LLM over urllib (no httpx on-device).
"""
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, "/opt/aura/src")
sys.path.insert(0, "/opt/aura-vision")
sys.path.insert(0, "/opt/aura-speech")

from aura.core.events import Event  # noqa: E402
from aura.memory.store import MemoryStore  # noqa: E402
import aura_npu_detect as vision  # noqa: E402
import aura_stt as stt  # noqa: E402
import aura_tts as tts  # noqa: E402

LLM_URL = os.environ.get("AURA_LLM_BASE_URL", "http://127.0.0.1:8080")
LLM_MODEL = os.environ.get("AURA_LLM_MODEL", "qwen2.5-0.5b")
DB = os.environ.get("AURA_DB", "/opt/aura/aura_live.db")
STILL = os.environ.get("AURA_IMG", "/opt/aura-vision/data/bus.jpg")
MIC = os.environ.get("AURA_MIC", "plughw:0,1")        # ALSA capture, auto-resampled
SPK = os.environ.get("AURA_SPK", "plughw:0,0")        # ALSA playback (speakers)
LOCATION = os.environ.get("AURA_LOCATION", "living room")


# ---- live capture helpers ------------------------------------------------
def record_mic(seconds):
    """Record from the live mic to a 16kHz mono WAV whisper can read."""
    wav = tempfile.mktemp(suffix=".wav")
    # plughw + -r 16000 lets ALSA resample the 48kHz codec down to 16kHz.
    r = subprocess.run(
        ["arecord", "-D", MIC, "-f", "S16_LE", "-r", "16000", "-c", "1",
         "-d", str(seconds), wav],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return wav if r.returncode == 0 and os.path.exists(wav) else None


def play(wav):
    """Play a WAV through the connected speakers."""
    subprocess.run(["aplay", "-q", "-D", SPK, wav], stderr=subprocess.DEVNULL)


def grab_frame():
    """Try to grab a LIVE camera frame; return (path, source) or (None, None)."""
    try:
        import cv2
        for idx in (0, 1, 2):
            cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
            ok, frame = (cap.read() if cap.isOpened() else (False, None))
            cap.release()
            if ok and frame is not None:
                jpg = tempfile.mktemp(suffix=".jpg")
                cv2.imwrite(jpg, frame)
                return jpg, "live camera /dev/video%d" % idx
    except Exception:
        pass
    return None, None


def perceive_scene(store):
    """Grab a frame (live if possible, else still) and run vision on the NPU."""
    frame, src = grab_frame()
    if frame is None:
        frame, src = STILL, "still image (%s) — no live camera" % os.path.basename(STILL)
    events = vision.detect(frame, location=LOCATION)
    counts = {}
    for e in events:
        counts[e["entities"][0]] = counts.get(e["entities"][0], 0) + 1
        store.add_event(Event(event=e["event"], type="detection", source="vision",
                              entities=e["entities"], location=e["location"],
                              confidence=e["confidence"]))
    scene = ", ".join("%d %s" % (n, l) for l, n in counts.items()) or "nothing"
    return scene, src, counts


# ---- reasoning -----------------------------------------------------------
def llm_answer(store, question, max_tokens=200):
    ctx = "\n".join("- %s (%s)" % (e.event, e.location or "?")
                    for e in store.query() if e.type == "detection")
    system = ("You are AURA, a privacy-first physical-AI agent. Answer using ONLY "
              "the observed events provided. Be concise and conversational.")
    body = json.dumps({
        "model": LLM_MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user",
                      "content": "Observed events:\n%s\n\nQuestion: %s" % (ctx, question)}],
        "temperature": 0.2, "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(LLM_URL + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)["choices"][0]["message"]["content"].strip()


def one_turn(store, question, speak=True):
    scene, src, counts = perceive_scene(store)
    print("  [SEE  ] %s  (%s)" % (scene, src))
    print("  [THINK] ...")
    answer = llm_answer(store, question)
    print("  [AURA ] %s" % answer)
    # act: trivial actuator grounded in the real vision count
    people = counts.get("person", 0)
    act = "porch light ON (%d person)" % people if people else "porch light OFF (no person)"
    store.add_event(Event(event="set_light: " + act, type="action", source="agent",
                          entities=["light"], location="porch"))
    if speak:
        try:
            wav = tts.synthesize(answer, "/tmp/aura_reply.wav")
            play(wav)
        except Exception as exc:
            print("  [speak failed: %s]" % exc)


def main():
    print("=" * 64)
    print("AURA live loop on IQ8  —  mic=%s  spk=%s  llm=%s" % (MIC, SPK, LLM_MODEL))
    print("  <Enter> speak a question | 't <text>' type | 'look' | 'secs N' | 'q'")
    print("=" * 64)
    store = MemoryStore(DB).connect()
    secs = int(os.environ.get("AURA_SECS", "5"))
    try:
        while True:
            cmd = input("\naura> ").strip()
            if cmd in ("q", "quit", "exit"):
                break
            if cmd.startswith("secs "):
                secs = int(cmd.split()[1]); print("  record seconds =", secs); continue
            if cmd == "look":
                scene, src, _ = perceive_scene(store)
                print("  [SEE] %s  (%s)" % (scene, src)); continue
            if cmd.startswith("t "):
                one_turn(store, cmd[2:].strip()); continue
            # default: record from the live mic
            print("  [HEAR ] recording %ds from mic (speak now) ..." % secs)
            wav = record_mic(secs)
            if not wav:
                print("  [mic capture failed on %s — try 't <text>']" % MIC); continue
            q = stt.transcribe(wav)
            os.unlink(wav)
            if not q:
                print("  [heard nothing]"); continue
            print("  [HEARD] %s" % q)
            one_turn(store, q)
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        store.close()
        print("\nbye.")


if __name__ == "__main__":
    sys.exit(main())
