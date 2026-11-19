"""Thin SSH/SCP wrapper around the OS ``ssh`` and ``scp`` binaries.

Why not paramiko? It would add a 1.5 MB native-extension dependency,
and we'd lose the user's existing ~/.ssh/config + agent integration.
The OS binaries are shipped on every modern Windows/macOS/Linux.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SSHTarget:
    host: str
    user: str = "root"
    port: int = 22
    key: Path | None = None
    connect_timeout_s: int = 5

    def base_args(self, *, is_scp: bool = False) -> list[str]:
        """Common ssh/scp options.

        ``scp`` and ``ssh`` disagree on the port flag: ssh uses lowercase
        ``-p``, but scp uses UPPERCASE ``-P`` (lowercase ``-p`` means "preserve
        mtime/mode" to scp and is silently ignored — the connection then
        defaults to port 22). Pass ``is_scp=True`` from the scp path so the
        right flag is emitted. (IQ-9075 retrospective: silent scp port bug.)
        """
        port_flag = "-P" if is_scp else "-p"
        args = [
            "-o", f"ConnectTimeout={self.connect_timeout_s}",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "BatchMode=yes",  # never prompt for password
            port_flag, str(self.port),
        ]
        if self.key:
            args += ["-i", str(self.key)]
        return args

    def user_at_host(self) -> str:
        return f"{self.user}@{self.host}"


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    elapsed_ms: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _check_ssh_available() -> str:
    exe = shutil.which("ssh")
    if exe is None:
        raise RuntimeError(
            "OS 'ssh' not found on PATH. Install OpenSSH (Windows: 'Add Optional "
            "Feature' -> OpenSSH Client; Linux/macOS: usually preinstalled)."
        )
    return exe


def run_remote(
    target: SSHTarget,
    remote_cmd: str | Sequence[str],
    *,
    timeout_s: int = 30,
) -> CommandResult:
    """Run a command on the remote board via SSH and capture output.

    ``remote_cmd`` may be a string (executed by the remote shell as-is)
    or a sequence of args (joined with spaces; quoting is the caller's
    responsibility for now).
    """
    import time as _time

    ssh = _check_ssh_available()
    if isinstance(remote_cmd, str):
        cmd_str = remote_cmd
    else:
        cmd_str = " ".join(str(p) for p in remote_cmd)

    full = [ssh, *target.base_args(), target.user_at_host(), cmd_str]
    start = _time.perf_counter()
    try:
        # encoding + errors="replace": remote boards emit non-UTF-8 bytes
        # (kernel logs, tool banners) that would otherwise crash report
        # generation with a UnicodeDecodeError. (IQ-9075 retrospective.)
        result = subprocess.run(
            full,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as e:
        elapsed = (_time.perf_counter() - start) * 1000
        return CommandResult(
            returncode=124,
            stdout=e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or ""),
            stderr=(
                f"SSH command timed out after {timeout_s}s. If the board is unreachable, "
                f"check the network/host {target.host}:{target.port}."
            ),
            elapsed_ms=elapsed,
        )
    elapsed = (_time.perf_counter() - start) * 1000
    # ssh exits 255 for connection-level failures (host down, refused, auth).
    # Turn that into an explicit, actionable message instead of a bare code.
    stderr = result.stderr
    if result.returncode == 255:
        stderr = (
            f"Board unreachable at {target.user_at_host()}:{target.port} — "
            f"ssh could not connect (host down, wrong port/key, or refused). "
            f"Original ssh error: {result.stderr.strip()}"
        )
    return CommandResult(
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=stderr,
        elapsed_ms=elapsed,
    )


def push_file(
    target: SSHTarget,
    src: Path,
    dst: str,
    *,
    timeout_s: int = 120,
    check_space: bool = True,
) -> CommandResult:
    """Copy a local file to the board via scp.

    When ``check_space`` is set, a pre-flight ``df`` on the destination
    directory verifies there is room for the file before starting the transfer
    — otherwise scp fails partway through with an unhelpful error (IQ-9075
    retrospective). The check is best-effort: if ``df`` can't run, the copy
    proceeds anyway.
    """
    import time as _time

    scp = shutil.which("scp")
    if scp is None:
        raise RuntimeError("OS 'scp' not found on PATH. Install OpenSSH client.")

    src = Path(src)
    if check_space and src.exists():
        space_err = _preflight_space(target, src, dst, timeout_s=target.connect_timeout_s + 10)
        if space_err is not None:
            return space_err

    # scp needs the UPPERCASE -P for port (see SSHTarget.base_args).
    args = [scp, *target.base_args(is_scp=True), str(src), f"{target.user_at_host()}:{dst}"]
    start = _time.perf_counter()
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(124, "", f"scp timeout after {timeout_s}s", (_time.perf_counter() - start) * 1000)
    return CommandResult(
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        elapsed_ms=(_time.perf_counter() - start) * 1000,
    )


def _preflight_space(
    target: SSHTarget,
    src: Path,
    dst: str,
    *,
    timeout_s: int = 15,
) -> CommandResult | None:
    """Return a CommandResult error if the board lacks room for ``src``.

    Returns ``None`` when there's enough space OR the check couldn't run
    (best-effort — never blocks a transfer on an inconclusive probe).
    """
    try:
        need_bytes = src.stat().st_size
    except OSError:
        return None

    # df -Pk on the destination's parent directory → available 1K-blocks.
    dst_dir = dst.rsplit("/", 1)[0] or "/"
    probe = run_remote(target, f"df -Pk {dst_dir!r} 2>/dev/null | tail -1", timeout_s=timeout_s)
    if not probe.ok or not probe.stdout.strip():
        return None  # inconclusive — let scp try
    parts = probe.stdout.split()
    # df -Pk columns: Filesystem 1K-blocks Used Available Capacity Mounted
    if len(parts) < 4:
        return None
    try:
        avail_bytes = int(parts[3]) * 1024
    except ValueError:
        return None
    if need_bytes > avail_bytes:
        return CommandResult(
            returncode=28,  # ENOSPC
            stdout="",
            stderr=(
                f"Not enough space on {target.host}:{dst_dir} — need "
                f"{need_bytes / 1e6:.1f} MB, only {avail_bytes / 1e6:.1f} MB free. "
                f"Free up space on the board before pushing."
            ),
            elapsed_ms=0.0,
        )
    return None
