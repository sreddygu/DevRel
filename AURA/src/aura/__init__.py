# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""AURA — Autonomous Understanding & Responsive Agent.

A privacy-first Physical-AI agent that sees, hears, remembers, reasons, and
acts entirely on-device on the Arduino VENTUNO Q — no cloud dependency.

    Eyes. Ears. Memory. Intelligence. Action.

The package is organized as a perceive → remember → reason → act pipeline:

    aura.vision     👁️  cameras + YOLO/VLM        → Events        (Milestone 1)
    aura.speech     👂🗣️  Whisper STT + MeloTTS                     (Milestone 2)
    aura.memory     📚  SQLite + vector store       ← Events        (Milestone 3)
    aura.agent      🧠🤖  local LLM + actuator tools                (Milestone 4/5)
    aura.dashboard  🖥️  FastAPI + Streamlit UI
    aura.core        the Event contract + the orchestration loop

Most modules are importable stubs at v0.1 — see docs/ROADMAP.md for the
milestone plan and which methods are implemented.
"""

from __future__ import annotations

__version__ = "0.1.0"

from aura.core.events import Event  # noqa: E402  (re-export the core contract)

__all__ = ["Event", "__version__"]
