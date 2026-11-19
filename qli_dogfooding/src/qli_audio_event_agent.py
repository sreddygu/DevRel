"""Capture audio and classify simple sound activity by RMS level.

Workflow: Audio Event Agent.
Requirements: Python 3, ALSA ``arecord``, and a 16-bit PCM capture device.
The module records only for the requested duration and uses a temporary file
unless ``--wav`` is supplied.

Example::

    python3 qli_audio_event_agent.py --device default --duration 2 --threshold 150
"""

import argparse
import math
import struct
import subprocess
import tempfile
import wave
from pathlib import Path


WORKFLOWS = ("Audio Event Agent",)


def capture_audio(device: str, duration: int, output_path: Path) -> None:
    """Record mono 16-bit PCM audio from an ALSA device into a WAV file."""
    completed = subprocess.run(
        [
            "arecord",
            "-D",
            device,
            "-d",
            str(duration),
            "-f",
            "S16_LE",
            "-r",
            "48000",
            "-c",
            "1",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "arecord failed")


def calculate_rms(path: Path) -> float:
    """Return the root-mean-square amplitude of a 16-bit PCM WAV file."""
    with wave.open(str(path), "rb") as stream:
        if stream.getsampwidth() != 2:
            raise ValueError("Only 16-bit PCM WAV input is supported")
        frames = stream.readframes(stream.getnframes())
    if not frames:
        return 0.0
    samples = struct.unpack("<" + "h" * (len(frames) // 2), frames)
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples))


def main() -> None:
    """Capture or analyze audio and print the RMS event classification."""
    parser = argparse.ArgumentParser(
        description="Capture device audio and report a simple RMS event classification."
    )
    parser.add_argument("--device", default="hw:0,1")
    parser.add_argument("--duration", type=int, default=2)
    parser.add_argument("--threshold", type=float, default=150.0)
    parser.add_argument("--wav", type=Path)
    parser.add_argument("--list-workflows", action="store_true")
    args = parser.parse_args()

    if args.list_workflows:
        print("\n".join(WORKFLOWS))
        return

    if args.wav:
        wav_path = args.wav
        capture_audio(args.device, args.duration, wav_path)
        rms = calculate_rms(wav_path)
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = Path(temp_dir) / "capture.wav"
            capture_audio(args.device, args.duration, wav_path)
            rms = calculate_rms(wav_path)

    event = "AUDIO_EVENT" if rms >= args.threshold else "QUIET"
    print(f"event={event} rms={rms:.2f} threshold={args.threshold:.2f}")


if __name__ == "__main__":
    main()
