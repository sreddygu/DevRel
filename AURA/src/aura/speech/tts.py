# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""Text-to-speech (Milestone 2).

Speaks AURA's responses aloud through the default audio output, running
locally on the VENTUNO Q. The synth engine is imported/spawned lazily inside
:meth:`load` / :meth:`synthesize`, so this module imports on the base install.

Two backends are supported out of the box:

- ``"piper"`` — the `piper` CLI (a small, fast, fully-local neural TTS that
  ships as a single prebuilt binary + ``.onnx`` voice). This is the on-device
  path: no Python deps, mirrors the llama.cpp/whisper.cpp binary approach.
- a custom ``backend`` callable (``text -> wav_bytes``) — used by tests.

``synthesize`` returns/writes a WAV; ``speak`` plays it on the default output.
"""

from __future__ import annotations

import shutil
import subprocess
import wave
from collections.abc import Callable

Backend = Callable[[str], bytes]


class TextToSpeech:
    """Local text-to-speech synthesizer.

    Args:
        voice: Voice/speaker id. For piper this is the path to a ``.onnx``
            voice model (e.g. ``en_US-amy-medium.onnx``).
        backend: Optional ``text -> wav_bytes`` callable. If given, it is used
            instead of piper (tests / alternate engines).
        piper_bin: Name/path of the piper executable (default ``"piper"``).
    """

    def __init__(
        self,
        voice: str = "EN-default",
        *,
        backend: Backend | None = None,
        piper_bin: str = "piper",
    ) -> None:
        self.voice = voice
        self.piper_bin = piper_bin
        self._backend = backend

    def load(self) -> TextToSpeech:
        """Initialize the TTS engine.

        No-op with an injected ``backend``; otherwise verifies the piper CLI is
        on ``PATH`` and wires it as the backend.
        """
        if self._backend is not None:
            return self
        if shutil.which(self.piper_bin) is None:
            raise RuntimeError(
                f"piper executable {self.piper_bin!r} not found on PATH. "
                "Install piper or pass a custom backend."
            )
        self._backend = self._piper_backend
        return self

    def _piper_backend(self, text: str) -> bytes:
        """Run piper to render ``text`` to WAV bytes on stdout."""
        proc = subprocess.run(
            [self.piper_bin, "--model", self.voice, "--output_file", "-"],
            input=text.encode("utf-8"),
            capture_output=True,
            check=True,
        )
        return proc.stdout

    def synthesize(self, text: str, *, out_path: str | None = None) -> bytes:
        """Render ``text`` to WAV bytes, also writing to ``out_path`` if given."""
        if self._backend is None:
            self.load()
        wav = self._backend(text)
        if out_path is not None:
            with open(out_path, "wb") as fh:
                fh.write(wav)
        return wav

    def speak(self, text: str) -> None:
        """Synthesize and play ``text`` on the default output device."""
        wav = self.synthesize(text)
        self._play(wav)

    def _play(self, wav: bytes) -> None:
        """Play WAV bytes via sounddevice (lazy import)."""
        import io  # noqa: PLC0415

        import numpy as np  # noqa: PLC0415
        import sounddevice as sd  # noqa: PLC0415 — lazy heavy import

        with wave.open(io.BytesIO(wav), "rb") as wf:
            rate = wf.getframerate()
            n = wf.getnframes()
            raw = wf.readframes(n)
        audio = np.frombuffer(raw, dtype=np.int16).astype("float32") / 32768.0
        sd.play(audio, samplerate=rate)
        sd.wait()
