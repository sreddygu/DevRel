"""A warm audio output: one PipeWire stream kept open, fed in real time, so a gesture does not pay a player start-up.

Starting a player per gesture costs 124 to 240 ms on the IQ8 before the sound server has the first sample (and more when the
audio device is closed). Here `pw-cat` is started once and a writer thread sends 10 ms chunks of silence; `play()` swaps in a
clip's samples for the next chunk, `stop()` swaps back to silence.

The pipe to `pw-cat` is capped at 4096 bytes so audio can never queue up ahead of playback and turn into latency.
Linux with PipeWire only. Samples are mono 16-bit at `rate` (48000 avoids resampling inside the sound server).
"""

from __future__ import annotations

import fcntl
import subprocess
import threading
import time
import wave

import numpy as np

F_SETPIPE_SZ = 1031          # linux/fcntl.h; the minimum is one page
CHUNK_MS = 10


def load_pcm(path: str, rate: int) -> bytes:
    """Read a 16-bit wav, mix to mono, resample to `rate` (linear), return raw little-endian 16-bit bytes."""
    with wave.open(str(path)) as w:
        ch, width, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if width != 2:
        raise ValueError(f"{path}: only 16-bit wav is supported")
    x = np.frombuffer(raw, dtype="<i2").astype(np.float32).reshape(-1, ch).mean(axis=1)
    if sr != rate:
        t_new = np.arange(int(len(x) * rate / sr)) * (sr / rate)
        x = np.interp(t_new, np.arange(len(x)), x)
    return np.clip(x, -32768, 32767).astype("<i2").tobytes()


class WarmOutput:
    def __init__(self, rate: int = 48000, latency_ms: int = 20, target: str | None = None):
        self.rate = rate
        self.chunk = rate * CHUNK_MS // 1000 * 2           # bytes per 10 ms chunk
        cmd = ["pw-cat", "-p", "--raw", "--rate", str(rate), "--channels", "1", "--format", "s16", "--latency", f"{latency_ms}ms"]
        if target:
            cmd += ["--target", target]
        self.p = subprocess.Popen(cmd + ["-"], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        fcntl.fcntl(self.p.stdin.fileno(), F_SETPIPE_SZ, 4096)
        self._pcm: bytes | None = None
        self._pos = 0
        self._lock = threading.Lock()
        self._stop = False
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def play(self, pcm: bytes) -> None:
        """Start these samples at the next chunk, replacing whatever is playing."""
        with self._lock:
            self._pcm, self._pos = pcm, 0

    def stop(self) -> None:
        with self._lock:
            self._pcm = None

    def _next_chunk(self) -> bytes:
        with self._lock:
            if self._pcm is None:
                return b"\x00" * self.chunk
            c = self._pcm[self._pos:self._pos + self.chunk]
            self._pos += self.chunk
            if self._pos >= len(self._pcm):
                self._pcm = None
            return c.ljust(self.chunk, b"\x00")

    def _run(self) -> None:
        nxt = time.perf_counter() + 1.0                      # give pw-cat a moment to connect before the first chunk
        time.sleep(1.0)
        while not self._stop:
            try:
                self.p.stdin.write(self._next_chunk())       # blocks when the capped pipe is full: no backlog
                self.p.stdin.flush()
            except (BrokenPipeError, ValueError, OSError):
                break
            nxt += CHUNK_MS / 1000
            d = nxt - time.perf_counter()
            if d > 0:
                time.sleep(d)
            else:
                nxt = time.perf_counter()                    # fell behind (for example while connecting): do not burst to catch up

    def close(self) -> None:
        self._stop = True
        try:
            self.p.stdin.close()
        except Exception:
            pass
        self.p.terminate()
