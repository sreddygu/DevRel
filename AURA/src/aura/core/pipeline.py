# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""AuraPipeline — the perceive → remember → reason → act loop.

This is the conductor that wires the milestone modules together::

    cameras ─▶ vision ─┐
                       ├─▶ Events ─▶ memory ─▶ agent (LLM) ─▶ TTS / actuators
    mic ─▶ speech ─────┘

At v0.1 this is a stub: the wiring and the intended data flow are described,
but the run loop is not implemented. Each collaborator is injected so the
pieces can be developed and tested in isolation (see docs/ROADMAP.md).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aura.core.events import Event

if TYPE_CHECKING:  # imports for type hints only — no runtime/heavy-dep cost
    from aura.agent.llm import LocalLLM
    from aura.memory.store import MemoryStore
    from aura.speech.stt import SpeechToText
    from aura.speech.tts import TextToSpeech
    from aura.vision.detector import Detector


class AuraPipeline:
    """Orchestrates perception, memory, reasoning, and action.

    Collaborators are optional so partial pipelines can run as milestones land
    (e.g. vision + memory only, before the LLM exists).
    """

    def __init__(
        self,
        *,
        detector: Detector | None = None,
        memory: MemoryStore | None = None,
        llm: LocalLLM | None = None,
        stt: SpeechToText | None = None,
        tts: TextToSpeech | None = None,
    ) -> None:
        self.detector = detector
        self.memory = memory
        self.llm = llm
        self.stt = stt
        self.tts = tts

    def perceive(self, frame: object | None = None, *, location: str | None = None) -> list[Event]:
        """Pull one round of observations from the sensors into Events.

        Runs the :class:`Detector` over ``frame`` (any array the detector
        accepts), converts detections to Events, and persists each via
        :meth:`MemoryStore.add_event` when a memory store is attached. Returns
        the Events produced (empty list if there is no detector or no frame).
        """
        if self.detector is None or frame is None:
            return []
        detections = self.detector.detect(frame)
        events = self.detector.to_events(detections, location=location)
        if self.memory is not None:
            for ev in events:
                self.memory.add_event(ev)
        return events

    def ask(self, question: str, *, k: int = 5) -> str:
        """Answer a natural-language question about what AURA has observed.

        Milestone 3/4 — retrieve relevant Events from memory (semantic
        ``recall``), hand them to the local LLM as grounding context, and
        return the generated answer.
        """
        if self.memory is None or self.llm is None:
            raise RuntimeError("ask() needs both a memory store and an llm.")
        context = self.memory.recall(question, k=k)
        return self.llm.answer(question, context)

    def run(self, camera: object | None = None, *, location: str | None = None) -> None:
        """Continuous perceive → remember loop (blocking).

        Iterates frames from ``camera`` (anything exposing ``.frames()``, e.g.
        :class:`aura.vision.camera.Camera`) and calls :meth:`perceive` on each,
        persisting detection Events to memory. Stops when the frame source is
        exhausted (a finite image dir / video) or on ``KeyboardInterrupt``.
        """
        if camera is None or self.detector is None:
            raise RuntimeError("run() needs a camera frame source and a detector.")
        try:
            for frame in camera.frames():
                self.perceive(frame, location=location)
        except KeyboardInterrupt:  # pragma: no cover — interactive stop
            pass
