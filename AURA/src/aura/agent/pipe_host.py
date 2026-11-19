"""Persistent warm-model backend over the ``qnn_llm_host.exe`` named pipe.

AURA's :mod:`aura.agent.executorch_server` shim can already run Gemma-4 on the
Snapdragon NPU by shelling ExecuTorch's ``llama_main`` once per completion
(:class:`~aura.agent.executorch_server.ExecuTorchRunner`) — correct, but it pays
the full model-load + QNN-context-restore cost on *every* request, which is
punishing inside an agent loop that makes many tool round-trips.

``qnn_llm_host.exe`` (vendored under ``bin/`` — see ``bin/README.md``) is a
persistent variant that loads the model + restores the QNN context **once (~2s)
and keeps it warm**, serving newline-delimited JSON prompts over a Windows named
pipe (``\\\\.\\pipe\\<name>``). This module wraps that host as a drop-in
:class:`~aura.agent.executorch_server.TextGenerator`, so the existing OpenAI /
tool-call shim is reused unchanged — only the token source differs.

Two behaviors are inherited from the C++ host and drive the design here:

1. **One continuous KV-cache.** Every request advances the same conversation
   position; the underlying ``Runner::reset()`` is a no-op. There is no in-band
   way to start a fresh conversation — the only reset is restarting the process.
2. **Context overflow is a hard process abort**, not a catchable error.

AURA's shim is stateless: it re-renders the whole conversation (system prompt +
tool schemas + history) on every ``generate`` call. Feeding that to a host whose
KV-cache also accumulates would double-count context and abort fast. So
:class:`PipeHostManager` owns the process lifecycle: it keeps the host warm, and
before the running position would exceed a conservative ceiling it **respawns**
the host (kill → relaunch → re-warm) to reset the KV-cache, then replays the
current request against the fresh process. This is the "managed, stateless"
approach — warm-load speedup without the overflow abort.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

DEFAULT_PIPE_NAME = "gemma4"
# Compiled context for the shipped Gemma-4 E2B .pte is 4000 with a 128-token AR
# chunk → max usable = 4000 - 128 = 3872. 3800 leaves headroom (see
# models/README.md).
DEFAULT_SEQ_LEN_CEILING = 3800
_LISTENING_MARKER = "Listening on"


def build_host_env(
    qnn_sdk_root: str,
    backend_dir: str,
    *,
    hexagon_arch: int | str = 73,
    base_env: dict[str, str] | None = None,
) -> dict[str, str]:
    """Assemble the environment ``qnn_llm_host.exe`` needs, as a plain dict.

    Mirrors the three variables the QNN runtime needs (see ``bin/README.md``):

    * ``QNN_SDK_ROOT`` — root of the extracted QAIRT SDK.
    * ``Path`` — prepends the backend dir (holding ``qnn_executorch_backend.dll``)
      and ``<sdk>/lib/aarch64-windows-msvc`` (holding ``QnnHtp.dll`` et al.).
    * ``ADSP_LIBRARY_PATH`` — ``<sdk>/lib/hexagon-v<arch>/unsigned`` (the HTP skel
      ``.so`` and its ``.cat`` signature, co-located).

    Kept pure (no process launch, no ``os.environ`` mutation) so it is unit
    testable on any platform.
    """
    env = dict(base_env if base_env is not None else os.environ)
    sdk = qnn_sdk_root.rstrip("\\/")
    aarch64_lib = str(Path(sdk) / "lib" / "aarch64-windows-msvc")
    adsp = str(Path(sdk) / "lib" / f"hexagon-v{hexagon_arch}" / "unsigned")

    env["QNN_SDK_ROOT"] = sdk
    env["ADSP_LIBRARY_PATH"] = adsp
    existing_path = env.get("Path", env.get("PATH", ""))
    env["Path"] = os.pathsep.join(
        part for part in (backend_dir, aarch64_lib, existing_path) if part
    )
    return env


class PipeHostClient:
    """Thin transport for the newline-delimited JSON named-pipe protocol.

    One instance holds one open connection to ``\\\\.\\pipe\\<pipe_name>``. The
    protocol: write one JSON request line, read one JSON response line.

    * request: ``{"prompt", "system_prompt", "seq_len", "temperature",
      "include_metrics"}`` — only ``prompt`` is required.
    * response: ``{"ok": true, "text": ...}`` (plus ``metrics`` when requested),
      or ``{"ok": false, "error": ...}``.
    * ``{"cmd": "shutdown"}`` stops the host process.
    """

    def __init__(self, pipe_name: str = DEFAULT_PIPE_NAME) -> None:
        self.pipe_name = pipe_name
        self.pipe_path = rf"\\.\pipe\{pipe_name}"
        self._pipe: Any = None

    def connect(self, *, timeout: float = 30.0, poll_interval: float = 0.25) -> None:
        """Open the pipe, retrying until the host has created it or ``timeout``."""
        deadline = time.monotonic() + timeout
        last_err: OSError | None = None
        while time.monotonic() < deadline:
            try:
                # Byte-mode duplex pipe → open read+write in binary.
                self._pipe = open(self.pipe_path, "r+b", buffering=0)
                return
            except OSError as exc:  # pipe not created yet, or busy
                last_err = exc
                time.sleep(poll_interval)
        raise TimeoutError(
            f"could not connect to {self.pipe_path} within {timeout}s"
        ) from last_err

    def _require_pipe(self) -> Any:
        if self._pipe is None:
            self.connect()
        return self._pipe

    def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send one request object, return the parsed response object."""
        pipe = self._require_pipe()
        line = json.dumps(payload, separators=(",", ":")) + "\n"
        pipe.write(line.encode("utf-8"))
        pipe.flush()
        return self._read_response()

    def _read_response(self) -> dict[str, Any]:
        pipe = self._require_pipe()
        buffer = bytearray()
        while True:
            chunk = pipe.read(1)
            if not chunk:
                raise ConnectionError("pipe closed before a full response line")
            if chunk == b"\n":
                break
            buffer.extend(chunk)
        return json.loads(buffer.decode("utf-8"))

    def shutdown(self) -> None:
        """Ask the host to exit; ignore transport errors during teardown."""
        try:
            if self._pipe is not None:
                self.request({"cmd": "shutdown"})
        except (OSError, ConnectionError, ValueError):
            pass
        finally:
            self.close()

    def close(self) -> None:
        if self._pipe is not None:
            try:
                self._pipe.close()
            finally:
                self._pipe = None


# A spawner returns (process_handle, client) so tests can inject fakes without a
# real exe or named pipe. The default is _default_spawn below.
Spawner = Callable[["PipeHostManager"], tuple[Any, PipeHostClient]]


def _default_spawn(manager: PipeHostManager) -> tuple[Any, PipeHostClient]:
    """Launch ``qnn_llm_host.exe`` warm and return a connected client."""
    env = build_host_env(
        manager.qnn_sdk_root,
        manager.backend_dir,
        hexagon_arch=manager.hexagon_arch,
    )
    command = [
        manager.host_bin,
        "--model_path", manager.model_path,
        "--tokenizer_path", manager.tokenizer_path,
        "--decoder_model_version", manager.decoder_model_version,
        "--pipe_name", manager.pipe_name,
        "--seq_len", str(manager.seq_len_ceiling),
    ]
    proc = subprocess.Popen(
        command,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=manager.cwd,
    )

    # Warm-load barrier: wait for the host to announce the pipe is listening.
    deadline = time.monotonic() + manager.warmup_timeout
    assert proc.stdout is not None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"qnn_llm_host.exe exited during warmup (code {proc.returncode})"
            )
        line = proc.stdout.readline()
        if line and _LISTENING_MARKER in line:
            break
    else:
        proc.kill()
        raise TimeoutError(
            f"host did not report '{_LISTENING_MARKER}' within "
            f"{manager.warmup_timeout}s"
        )

    client = PipeHostClient(manager.pipe_name)
    client.connect(timeout=manager.warmup_timeout)
    return proc, client


class PipeHostManager:
    """Own a warm ``qnn_llm_host.exe`` and expose it as a ``TextGenerator``.

    Implements the same ``generate(prompt, *, max_new_tokens, temperature) -> str``
    contract as :class:`~aura.agent.executorch_server.ExecuTorchRunner`, so it drops
    straight into ``build_server`` and the existing OpenAI / tool-call shim.

    Because the host's KV-cache is continuous and cannot be reset in-band, the
    manager tracks a running position estimate and **respawns** the host before the
    position would exceed ``seq_len_ceiling`` — the only way to reset the cache.
    """

    def __init__(
        self,
        host_bin: str,
        model_path: str,
        tokenizer_path: str,
        *,
        decoder_model_version: str = "gemma4",
        pipe_name: str = DEFAULT_PIPE_NAME,
        seq_len_ceiling: int = DEFAULT_SEQ_LEN_CEILING,
        backend_dir: str = "",
        qnn_sdk_root: str = "",
        hexagon_arch: int | str = 73,
        temperature: float = 0.0,
        warmup_timeout: float = 60.0,
        cwd: str | None = None,
        chars_per_token: float = 4.0,
        spawner: Spawner | None = None,
    ) -> None:
        self.host_bin = host_bin
        self.model_path = model_path
        self.tokenizer_path = tokenizer_path
        self.decoder_model_version = decoder_model_version
        self.pipe_name = pipe_name
        self.seq_len_ceiling = seq_len_ceiling
        self.backend_dir = backend_dir
        self.qnn_sdk_root = qnn_sdk_root
        self.hexagon_arch = hexagon_arch
        self.temperature = temperature
        self.warmup_timeout = warmup_timeout
        self.cwd = cwd
        self.chars_per_token = chars_per_token
        self._spawner = spawner or _default_spawn

        self._proc: Any = None
        self._client: PipeHostClient | None = None
        # Running estimate of the host's KV-cache position (prompt + generated).
        self._position = 0

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        """Spawn the host warm if it isn't already running."""
        if self._client is None:
            self._proc, self._client = self._spawner(self)
            self._position = 0

    def _respawn(self) -> None:
        """Kill and relaunch the host to reset its continuous KV-cache."""
        self.close()
        self.start()

    def _estimate_tokens(self, text: str) -> int:
        return max(1, int(len(text) / self.chars_per_token))

    # -- TextGenerator -------------------------------------------------------

    def generate(
        self,
        prompt: str,
        *,
        max_new_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Run one completion on the warm host, respawning if near the ceiling."""
        self.start()

        headroom = max_new_tokens if max_new_tokens and max_new_tokens > 0 else 256
        projected = self._position + self._estimate_tokens(prompt) + headroom
        if projected >= self.seq_len_ceiling and self._position > 0:
            # Reset the KV-cache before it overflows (a hard abort otherwise).
            self._respawn()

        assert self._client is not None
        payload: dict[str, Any] = {
            "prompt": prompt,
            "seq_len": self.seq_len_ceiling,
            "temperature": self.temperature if temperature is None else temperature,
        }
        response = self._client.request(payload)
        if not response.get("ok", False):
            raise RuntimeError(
                f"qnn_llm_host error: {response.get('error', 'unknown error')}"
            )
        text = str(response.get("text", ""))
        # Advance the running position by what we fed plus what came back.
        self._position += self._estimate_tokens(prompt) + self._estimate_tokens(text)
        return text

    # -- teardown ------------------------------------------------------------

    def close(self) -> None:
        """Shut the host down and drop the connection."""
        if self._client is not None:
            self._client.shutdown()
            self._client = None
        proc = self._proc
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except Exception:  # noqa: BLE001 — best-effort teardown
                        proc.kill()
            finally:
                self._proc = None
        self._position = 0

    def __enter__(self) -> PipeHostManager:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
