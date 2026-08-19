# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""👂🗣️ Speech — Whisper STT + MeloTTS (Milestone 2, "Ears" / Voice).

    mic ─▶ SpeechToText (Whisper) ─▶ text ─▶ agent
    agent ─▶ text ─▶ TextToSpeech (MeloTTS) ─▶ speaker

Heavy deps (``openai-whisper``, ``sounddevice``, MeloTTS) are in the ``speech``
optional-dependency group and imported lazily.
"""

from __future__ import annotations

from aura.speech.stt import SpeechToText
from aura.speech.tts import TextToSpeech

__all__ = ["SpeechToText", "TextToSpeech"]
