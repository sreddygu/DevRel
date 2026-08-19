# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""Milestone 2 (Ears/Voice) demo — audio → transcript → Event → spoken reply.

Transcribes a WAV file (or the microphone) with Whisper, wraps the transcript
as a ``speech`` Event, and — if a TTS backend is available — speaks a reply.

    python examples/listen_demo.py path/to/question.wav   # transcribe a file
    python examples/listen_demo.py --mic                   # record 5s from mic

Needs the ``speech`` extra (``pip install -e ".[speech]"``) for real Whisper /
microphone capture, and piper on PATH for spoken output. Without a TTS engine
the reply is printed instead of spoken, so the wiring is still visible.
"""

from __future__ import annotations

import sys

from aura.config import load_settings
from aura.speech.stt import SpeechToText
from aura.speech.tts import TextToSpeech


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    settings = load_settings()

    stt = SpeechToText(settings.whisper_model).load()
    if argv and argv[0] == "--mic":
        print("Recording 5s from microphone…")
        text = stt.listen(seconds=5.0)
    elif argv:
        text = stt.transcribe(argv[0])
    else:
        print("Usage: listen_demo.py <audio.wav> | --mic", file=sys.stderr)
        return 2

    event = stt.to_event(text)
    print("== Transcript ==")
    print(text, "\n")
    print("== Event ==")
    print(event.to_json(), "\n")

    reply = f"You said: {text}"
    try:
        TextToSpeech(settings.tts_voice).speak(reply)
        print("== Spoke reply via TTS ==")
    except Exception as exc:  # noqa: BLE001 — demo: fall back to printing
        print(f"[no TTS engine: {type(exc).__name__}] reply would be: {reply}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
