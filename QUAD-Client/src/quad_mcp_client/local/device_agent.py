"""Client-side device profiling agent.

When the QUAD MCP server is remote (e.g. cloud), it cannot reach a board on the
developer's own bench (USB/ADB invisible, LAN IPs unroutable). So the server
hands the client a *plan* — files to push + shell commands to run — and this
module executes that plan locally over the client's own SSH/ADB, then hands the
raw outputs back to the server (via ``profile_device_report``) for parsing.

The client stays a thin executor: it does not classify models, build commands,
parse latency, or generate reports — all of that is the server's job (one
source of truth). This module only moves bytes and runs commands on the local
transport, exactly as the plan dictates.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from .board.ssh import CommandResult, push_file, run_remote


def _run(transport: str, target: Any, shell: str, *, timeout_s: int) -> CommandResult:
    """Run one shell command over the client's local transport."""
    if transport == "adb":
        from .board.adb import ADBTarget, adb_shell

        tgt = target if isinstance(target, ADBTarget) else ADBTarget(serial=str(target or ""))
        return adb_shell(tgt, shell, timeout_s=timeout_s)
    # ssh / local (local = ssh to empty host is not meaningful; callers pass an
    # SSHTarget with the board's host, or use adb).
    return run_remote(target, shell, timeout_s=timeout_s)


def _push(transport: str, target: Any, src: Path, dst: str, *, timeout_s: int) -> CommandResult:
    if transport == "adb":
        from .board.adb import ADBTarget, adb_push

        tgt = target if isinstance(target, ADBTarget) else ADBTarget(serial=str(target or ""))
        return adb_push(tgt, src, dst, timeout_s=timeout_s)
    return push_file(target, src, dst, timeout_s=timeout_s)


def execute_plan(
    plan: dict[str, Any],
    *,
    model_path: str | Path,
    transport: str,
    target: Any,
    probe_device: bool = True,
) -> dict[str, Any]:
    """Execute a server-issued device plan locally; return outputs for the server.

    Args:
        plan: the dict from the ``profile_device_plan`` MCP tool.
        model_path: the client-local model file (the developer has it on the
            machine the board is attached to).
        transport: "ssh" | "adb".
        target: an :class:`SSHTarget` (ssh) or an ADB serial string / ADBTarget.
        probe_device: collect a small device_info bundle (arch/os/ram).

    Returns:
        ``{"step_outputs": [{id, returncode, stdout, stderr}], "device_info": {...},
          "log": [...], "error": "" }`` — pass step_outputs + device_info straight
        into ``profile_device_report``.
    """
    out: dict[str, Any] = {"step_outputs": [], "device_info": {}, "log": [], "error": ""}
    model = Path(model_path)
    if not model.is_file():
        out["error"] = f"model not found on client: {model}"
        return out

    workspace = str(plan.get("workspace", "/data/local/tmp/quad")).rstrip("/")

    # Ensure the models dir exists on the device.
    mk = _run(transport, target, f"mkdir -p {workspace}/models", timeout_s=15)
    out["log"].append(f"mkdir models: rc={mk.returncode}")

    # Push files named by the plan. role=model → the client-local model; a file
    # carrying inline `content` (e.g. the bench script) is written then pushed.
    for pf in plan.get("files", []):
        role = pf.get("role")
        remote_path = pf.get("remote_path", "")
        if role == "model":
            r = _push(transport, target, model, remote_path, timeout_s=300)
            out["log"].append(f"push model -> {remote_path}: rc={r.returncode}")
            if not r.ok:
                out["error"] = f"model push failed: {r.stderr.strip()[:200]}"
                return out
        elif pf.get("content"):
            with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as fh:
                fh.write(pf["content"])
                tmp = fh.name
            try:
                r = _push(transport, target, Path(tmp), remote_path, timeout_s=60)
                out["log"].append(f"push {role} -> {remote_path}: rc={r.returncode}")
                if not r.ok:
                    out["error"] = f"{role} push failed: {r.stderr.strip()[:200]}"
                    return out
            finally:
                Path(tmp).unlink(missing_ok=True)

    # Run each step in order, collecting raw outputs for the server to parse.
    for step in plan.get("steps", []):
        r = _run(transport, target, step.get("shell", ""), timeout_s=int(step.get("timeout_s", 90)))
        out["step_outputs"].append({
            "id": step.get("id", ""),
            "returncode": r.returncode,
            "stdout": r.stdout,
            "stderr": r.stderr,
        })
        out["log"].append(f"step {step.get('id')}: rc={r.returncode} ({r.elapsed_ms:.0f} ms)")

    if probe_device:
        out["device_info"] = _probe(transport, target)

    return out


def _probe(transport: str, target: Any) -> dict[str, str]:
    """Small live device probe (arch/os/ram) — mirrors the server-side probe."""
    info: dict[str, str] = {}
    probes = {
        "arch": "uname -m",
        "os": "grep PRETTY_NAME /etc/os-release 2>/dev/null | cut -d= -f2",
        "ram_mb": "free -m 2>/dev/null | awk '/Mem:/{print $2}'",
    }
    for key, cmd in probes.items():
        try:
            r = _run(transport, target, cmd, timeout_s=10)
            if r.ok and r.stdout.strip():
                info[key] = r.stdout.strip().strip('"')
        except Exception:  # noqa: BLE001 — probes are best-effort
            pass
    return info
