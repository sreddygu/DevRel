"""Write three short test tones (clip_a/b/c.wav) and a lower, quieter "_filtered" variant of each.

Stand-ins for a real clip library, so the live mixer can be tried without a generated song.

    python make_test_clips.py clips
"""

from __future__ import annotations

import math
import struct
import sys
import wave
from pathlib import Path


def tone(path: Path, freq: float, amp: int, dur: float = 2.0, sr: int = 16000) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", int(amp * math.sin(2 * math.pi * freq * i / sr))) for i in range(int(sr * dur))))


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "clips")
    out.mkdir(parents=True, exist_ok=True)
    for name, f in (("clip_a", 330), ("clip_b", 440), ("clip_c", 550)):
        tone(out / f"{name}.wav", f, 8000)
        tone(out / f"{name}_filtered.wav", f / 2, 3000)
    print(f"Wrote clips to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
