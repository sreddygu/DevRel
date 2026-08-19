# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""Milestone 2 (Speech) tests.

Run on the base install by injecting backends, so neither Whisper nor piper
(nor any audio device) is needed. This exercises the STT/TTS wiring and the
Event bridge.
"""

from __future__ import annotations

import wave

import pytest

from aura.core.events import Event
from aura.speech.stt import SpeechToText
from aura.speech.tts import TextToSpeech


def test_stt_transcribe_with_backend() -> None:
    stt = SpeechToText(backend=lambda audio: "  hello there  ")
    assert stt.transcribe(object()) == "hello there"


def test_stt_load_noop_with_backend() -> None:
    calls = []
    stt = SpeechToText(backend=lambda audio: calls.append(audio) or "ok")
    assert stt.load() is stt  # does not try to import whisper
    assert stt.transcribe("x") == "ok"
    assert calls == ["x"]


def test_stt_to_event() -> None:
    stt = SpeechToText(backend=lambda a: "what happened today?")
    ev = stt.to_event(stt.transcribe(b""))
    assert isinstance(ev, Event)
    assert ev.event == "what happened today?"
    assert ev.type == "speech"
    assert ev.source == "speech"


def _valid_wav_bytes() -> bytes:
    import io

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16_000)
        wf.writeframes(b"\x00\x00" * 16)
    return buf.getvalue()


def test_tts_synthesize_with_backend(tmp_path) -> None:
    wav = _valid_wav_bytes()
    tts = TextToSpeech(backend=lambda text: wav)
    out = tmp_path / "out.wav"
    result = tts.synthesize("hello", out_path=str(out))
    assert result == wav
    assert out.read_bytes() == wav


def test_tts_load_requires_piper_or_backend() -> None:
    tts = TextToSpeech(piper_bin="definitely-not-a-real-binary-xyz")
    with pytest.raises(RuntimeError, match="piper"):
        tts.load()
