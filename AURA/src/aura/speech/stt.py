# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""Whisper speech-to-text (Milestone 2).

Transcribes microphone audio (or a WAV file) to text using Whisper running
locally on the VENTUNO Q. ``whisper`` / ``sounddevice`` are imported lazily
inside the methods that need them, so this module imports on the base install.

The actual transcription is delegated to a ``backend`` callable
(``audio -> text``). By default that's a lazily-loaded Whisper model, but tests
(and the on-device whisper.cpp path) can inject their own — the same seam
``LocalLLM`` uses for its HTTP transport.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from aura.core.events import Event

Backend = Callable[[Any], str]


class SpeechToText:
    """Local Whisper transcriber.

    Args:
        model_name: Whisper size — ``"tiny"`` / ``"base"`` / ``"small"``.
            Smaller = faster on-device.
        backend: Optional ``audio -> text`` callable. If given, it is used
            instead of loading Whisper (used by tests and the whisper.cpp
            on-device path).
        sample_rate: Capture sample rate for :meth:`listen` (Whisper wants 16 kHz).
    """

    def __init__(
        self,
        model_name: str = "base",
        *,
        backend: Backend | None = None,
        sample_rate: int = 16_000,
    ) -> None:
        self.model_name = model_name
        self.sample_rate = sample_rate
        self._backend = backend
        self._model: Any = None

    def load(self) -> SpeechToText:
        """Load the Whisper model (lazy-imports whisper).

        No-op when a ``backend`` was injected.
        """
        if self._backend is not None:
            return self
        import whisper  # noqa: PLC0415 — lazy heavy import

        self._model = whisper.load_model(self.model_name)

        def _whisper_backend(audio: Any) -> str:
            result = self._model.transcribe(audio, fp16=False)
            return str(result.get("text", "")).strip()

        self._backend = _whisper_backend
        return self

    def transcribe(self, audio: Any) -> str:
        """Transcribe an audio buffer or file path to text.

        ``audio`` may be a path to a WAV/MP3, or a float32 numpy array of mono
        samples at :attr:`sample_rate` (what Whisper expects).
        """
        if self._backend is None:
            self.load()
        return self._backend(audio).strip()

    def listen(self, *, seconds: float = 5.0) -> str:
        """Record from the default microphone and transcribe."""
        import numpy as np  # noqa: PLC0415
        import sounddevice as sd  # noqa: PLC0415 — lazy heavy import

        frames = int(seconds * self.sample_rate)
        recording = sd.rec(frames, samplerate=self.sample_rate, channels=1, dtype="float32")
        sd.wait()
        audio = np.squeeze(recording)
        return self.transcribe(audio)

    def to_event(self, text: str) -> Event:
        """Wrap a transcript as a ``speech`` Event (no model needed)."""
        return Event(event=text, type="speech", source="speech")
