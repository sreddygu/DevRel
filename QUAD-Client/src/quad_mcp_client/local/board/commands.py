"""High-level UNO Q board operations.

Each function corresponds to one ``quad-client unoq <cmd>`` subcommand
and replaces what used to be inline ``ssh user@host "..."`` Bash
strings in the ``quad-unoq`` skill markdown. They take a typed
``SSHTarget`` and return a ``BoardOpResult`` so callers (the CLI, the
skill, future MCP wrappers) can render results consistently.

Power, performance, stability, and KPI semantics intentionally mirror
the original skill -- no behavior changes here, only ergonomics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .ssh import SSHTarget, push_file, run_remote


@dataclass
class BoardOpResult:
    op: str
    ok: bool
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    elapsed_ms: float = 0.0


def _bundle(op: str, *cmds: tuple[str, str], target: SSHTarget, timeout_s: int = 60) -> BoardOpResult:
    """Run several ``(label, cmd)`` pairs in one SSH session and return them."""
    details: dict[str, Any] = {}
    failures: list[str] = []
    total_elapsed = 0.0
    for label, cmd in cmds:
        r = run_remote(target, cmd, timeout_s=timeout_s)
        details[label] = {
            "stdout": r.stdout.strip()[:2000],
            "stderr": r.stderr.strip()[:500],
            "returncode": r.returncode,
        }
        total_elapsed += r.elapsed_ms
        if not r.ok:
            failures.append(label)
    ok = not failures
    summary = "all probes succeeded" if ok else f"failed: {', '.join(failures)}"
    return BoardOpResult(op=op, ok=ok, summary=summary, details=details, elapsed_ms=total_elapsed)


# ─── 1. status ─────────────────────────────────────────────────────────


def status(target: SSHTarget) -> BoardOpResult:
    return _bundle(
        "status",
        ("alive", "echo ALIVE"),
        ("uname", "uname -a"),
        ("os_release", "cat /etc/os-release 2>/dev/null | head -8"),
        ("memory", "free -m"),
        ("disk", "df -h /"),
        ("loadavg", "cat /proc/loadavg"),
        ("hexagon_dmesg", "dmesg 2>/dev/null | grep -i hexagon | tail -5 || true"),
        ("thermal", "for f in /sys/class/thermal/thermal_zone*/temp; do [ -f \"$f\" ] && echo \"$f=$(cat $f)\"; done"),
        ("inference_procs", "ps aux | grep -E 'snpe-net-run|qnn-net-run|inference' | grep -v grep || true"),
        target=target,
    )


# ─── 2. configure (no-op except producing a TOML stanza) ───────────────


# Board configuration profiles. Previously the template hard-coded UNO Q
# specifics (soc=qcs2210, hexagon=v66, ram=2048), so it could not be used for
# any other board (IQ-9075 retrospective issues IQ9-8/22). Keyed by board slug.
_BOARD_PROFILES: dict[str, dict[str, Any]] = {
    "arduino-unoq": {
        "soc": "qcs2210",
        "hexagon": "v66",
        "max_ram_mb": 2048,
        "max_model_size_mb": 500,
        "preferred_runtime": "dsp",
        "snpe_root": "/opt/snpe/",
    },
    "iq9075": {
        # Dragonwing IQ-9075 EVK (QCS9075) — HTP v73, validated QLI 2.0.
        "soc": "qcs9075",
        "hexagon": "v73",
        "max_ram_mb": 8192,
        "max_model_size_mb": 2000,
        "preferred_runtime": "htp",
        "snpe_root": "/usr/lib/",
    },
}

_DEFAULT_BOARD = "arduino-unoq"


def configure_template(
    host: str,
    user: str = "root",
    workspace: str = "/data/local/tmp/quad/",
    board: str = _DEFAULT_BOARD,
    port: int = 22,
) -> BoardOpResult:
    """Emit a quad.toml [target.*] stanza for board configuration.

    ``board`` selects the SoC / Hexagon arch / RAM / runtime profile from
    :data:`_BOARD_PROFILES` so the template is portable across boards (not
    UNO Q-only). Unknown boards fall back to the UNO Q profile with a note.
    """
    slug = board.lower()
    spec = _BOARD_PROFILES.get(slug)
    note = ""
    if spec is None:
        spec = _BOARD_PROFILES[_DEFAULT_BOARD]
        slug = _DEFAULT_BOARD
        note = f"# NOTE: unknown board '{board}' — using {_DEFAULT_BOARD} defaults\n"

    toml = f"""{note}[target]
type = "linux-ssh"
board = "{slug}"
soc = "{spec['soc']}"
hexagon = "{spec['hexagon']}"

[target.ssh]
host = "{host}"
user = "{user}"
key = "~/.ssh/id_rsa"
port = {port}

[target.paths]
workspace = "{workspace}"
snpe_root = "{spec['snpe_root']}"
models = "{workspace}models/"
logs = "{workspace}logs/"

[target.constraints]
max_ram_mb = {spec['max_ram_mb']}
max_model_size_mb = {spec['max_model_size_mb']}
preferred_runtime = "{spec['preferred_runtime']}"
"""
    return BoardOpResult(
        op="configure",
        ok=True,
        summary=f"rendered TOML stanza for board '{slug}' (write this to quad.toml)",
        details={"toml": toml, "board": slug},
    )


# ─── 3. deploy ─────────────────────────────────────────────────────────


def deploy(
    target: SSHTarget,
    *,
    app_path: Path,
    model_path: Path,
    workspace: str = "/data/local/tmp/quad/",
) -> BoardOpResult:
    """Push app + model to the board and run a single inference smoke test."""
    if not app_path.exists():
        return BoardOpResult("deploy", False, f"app path missing: {app_path}")
    if not model_path.exists():
        return BoardOpResult("deploy", False, f"model path missing: {model_path}")

    # Pre-flight free space
    pre = run_remote(target, f"mkdir -p {workspace}models && df -h {workspace}", timeout_s=15)
    if not pre.ok:
        return BoardOpResult("deploy", False, f"pre-flight failed: {pre.stderr.strip()[:200]}")

    # Push artifacts
    push_app = push_file(target, app_path, f"{workspace}{app_path.name}", timeout_s=120)
    if not push_app.ok:
        return BoardOpResult("deploy", False, f"app push failed: {push_app.stderr.strip()[:200]}")
    push_model = push_file(target, model_path, f"{workspace}models/{model_path.name}", timeout_s=300)
    if not push_model.ok:
        return BoardOpResult("deploy", False, f"model push failed: {push_model.stderr.strip()[:200]}")

    # Smoke inference
    smoke = run_remote(
        target,
        f"cd {workspace} && ls -la {app_path.name} models/{model_path.name}",
        timeout_s=15,
    )
    return BoardOpResult(
        "deploy",
        ok=smoke.ok,
        summary=f"deployed {app_path.name} + {model_path.name}" if smoke.ok else "deploy verification failed",
        details={
            "pre_flight": pre.stdout.strip()[:500],
            "verify": smoke.stdout.strip()[:500],
            "smoke_stderr": smoke.stderr.strip()[:200],
        },
        elapsed_ms=push_app.elapsed_ms + push_model.elapsed_ms + smoke.elapsed_ms,
    )


# ─── 4. firmware (read-only checks; flashing is manual) ─────────────────


def firmware_info(target: SSHTarget) -> BoardOpResult:
    return _bundle(
        "firmware",
        ("build_info", "cat /etc/build-info 2>/dev/null || cat /etc/os-release | head -5"),
        ("kernel", "uname -r"),
        ("dsp_skel", "ls -la /usr/lib/rfsa/adsp/ 2>/dev/null | head -10"),
        ("snpe_libs", "ls /opt/snpe/lib 2>/dev/null | head -10"),
        target=target,
    )


# ─── 5. logs ───────────────────────────────────────────────────────────


def logs(target: SSHTarget, *, since_minutes: int = 60) -> BoardOpResult:
    return _bundle(
        "logs",
        ("dmesg_tail", "dmesg | tail -200"),
        ("journal_recent", f"journalctl --since '{since_minutes} minutes ago' --no-pager 2>/dev/null | tail -100 || echo '(no journalctl)'"),
        ("snpe_logs", "find /data/local/tmp/quad/logs -type f -name '*.log' 2>/dev/null | head -5"),
        ("dsp_trace", "cat /sys/kernel/debug/remoteproc/remoteproc*/trace0 2>/dev/null | tail -50 || echo '(no DSP trace)'"),
        ("tombstones", "ls /data/tombstones/ 2>/dev/null || echo '(no tombstones)'"),
        target=target,
    )


# ─── 6. debug ──────────────────────────────────────────────────────────


def debug(target: SSHTarget) -> BoardOpResult:
    return _bundle(
        "debug",
        ("dsp_state", "cat /sys/class/remoteproc/remoteproc0/state 2>/dev/null || echo '(no remoteproc0)'"),
        ("snpe_version", "snpe-net-run --version 2>&1 | head -1 || echo '(snpe-net-run not on device PATH)'"),
        ("kernel_errors", "dmesg | grep -iE 'error|fail|fault|panic' | tail -20"),
        ("recent_crashes", "ls -la /data/tombstones/ 2>/dev/null | tail -5 || true"),
        target=target,
    )


# ─── 7. perf ───────────────────────────────────────────────────────────


def perf(target: SSHTarget, *, model_path: str, duration_s: int = 30, perf_profile: str = "burst") -> BoardOpResult:
    cmd = (
        f"snpe-net-run --container {model_path} --use_dsp --perf_profile {perf_profile} "
        f"--duration {duration_s} --debug 2>&1 | grep -E 'Total Inference|Init Time' || true"
    )
    r = run_remote(target, cmd, timeout_s=duration_s + 30)
    return BoardOpResult(
        op="perf",
        ok=r.ok,
        summary=f"perf run ({perf_profile}, {duration_s}s)",
        details={"stdout": r.stdout, "stderr": r.stderr.strip()[:500]},
        elapsed_ms=r.elapsed_ms,
    )


# ─── 8. stability (orchestrate, don't block) ───────────────────────────


def stability_kickoff(
    target: SSHTarget,
    *,
    model_path: str,
    duration_s: int = 3600,
    workspace: str = "/data/local/tmp/quad/",
) -> BoardOpResult:
    """Start a soak test on the device. Returns immediately with the
    backgrounded PID; user pulls ``$workspace/logs/soak_result.txt`` later.
    """
    soak_cmd = (
        f"nohup bash -c 'PASS=0; FAIL=0; START=$(date +%s); "
        f"while [ $(($(date +%s) - START)) -lt {duration_s} ]; do "
        f"  if snpe-net-run --container {model_path} --use_dsp --perf_profile balanced "
        f"  >/dev/null 2>&1; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); fi; "
        f"done; "
        f"echo \"PASS=$PASS FAIL=$FAIL\" > {workspace}logs/soak_result.txt' "
        f"> {workspace}logs/soak.log 2>&1 & echo $!"
    )
    r = run_remote(target, soak_cmd, timeout_s=15)
    pid = r.stdout.strip().splitlines()[-1] if r.stdout else ""
    return BoardOpResult(
        op="stability",
        ok=r.ok and pid.isdigit(),
        summary=f"soak started (pid={pid}, duration={duration_s}s); pull {workspace}logs/soak_result.txt when done",
        details={"pid": pid, "stderr": r.stderr.strip()[:500]},
        elapsed_ms=r.elapsed_ms,
    )


# ─── 9. power ──────────────────────────────────────────────────────────


def power(target: SSHTarget) -> BoardOpResult:
    return _bundle(
        "power",
        ("ina_power", "cat /sys/bus/iio/devices/iio:device*/in_power*_raw 2>/dev/null | head -5 || echo '(no INA sensor)'"),
        ("cpu_freq", "for f in /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq; do [ -f $f ] && cat $f; done | tr '\\n' ' '"),
        ("gpu_freq", "cat /sys/class/kgsl/kgsl-3d0/gpuclk 2>/dev/null || echo '(no GPU freq)'"),
        ("thermal", "for f in /sys/class/thermal/thermal_zone*/temp; do [ -f \"$f\" ] && echo \"$f=$(cat $f)\"; done"),
        target=target,
    )


# ─── 10. app lifecycle ─────────────────────────────────────────────────


def app_lifecycle(target: SSHTarget, *, action: str, app_name: str) -> BoardOpResult:
    valid = {"start", "stop", "restart", "status"}
    if action not in valid:
        return BoardOpResult("app", False, f"action must be one of {valid}, got {action!r}")
    cmd = f"systemctl {action} quad-inference@{app_name} 2>&1 || journalctl -u quad-inference@{app_name} --no-pager -n 20"
    r = run_remote(target, cmd, timeout_s=15)
    return BoardOpResult(
        op=f"app:{action}",
        ok=r.ok,
        summary=f"systemctl {action} quad-inference@{app_name}",
        details={"stdout": r.stdout.strip()[:1000]},
        elapsed_ms=r.elapsed_ms,
    )


# ─── 11. ota ───────────────────────────────────────────────────────────


def ota(
    target: SSHTarget,
    *,
    archive: Path,
    workspace: str = "/data/local/tmp/quad/",
) -> BoardOpResult:
    if not archive.exists():
        return BoardOpResult("ota", False, f"archive missing: {archive}")
    push = push_file(target, archive, f"{workspace}updates/{archive.name}", timeout_s=300)
    if not push.ok:
        return BoardOpResult("ota", False, f"upload failed: {push.stderr.strip()[:200]}")
    apply = run_remote(
        target,
        f"cd {workspace} && tar xzf updates/{archive.name} -C apps/ && echo 'ok'",
        timeout_s=120,
    )
    return BoardOpResult(
        "ota",
        ok=apply.ok,
        summary=f"deployed {archive.name}" if apply.ok else "tar extraction failed",
        details={"stdout": apply.stdout.strip()[:500], "stderr": apply.stderr.strip()[:500]},
        elapsed_ms=push.elapsed_ms + apply.elapsed_ms,
    )


# ─── 12. test (E2E suite -- read result file from board) ───────────────


def run_test_suite(target: SSHTarget, *, workspace: str = "/data/local/tmp/quad/") -> BoardOpResult:
    cmd = f"cd {workspace} && [ -x run_tests.sh ] && bash run_tests.sh || echo 'no run_tests.sh deployed'"
    r = run_remote(target, cmd, timeout_s=600)
    return BoardOpResult(
        op="test",
        ok=r.ok,
        summary="ran run_tests.sh" if r.ok else "test runner missing or failed",
        details={"stdout": r.stdout, "stderr": r.stderr.strip()[:500]},
        elapsed_ms=r.elapsed_ms,
    )


# ─── Dispatcher (used by CLI for cleaner argparse mapping) ─────────────


def run_command(name: str, *args: Any, **kwargs: Any) -> BoardOpResult:
    fn = {
        "status": status,
        "configure": configure_template,
        "deploy": deploy,
        "firmware": firmware_info,
        "logs": logs,
        "debug": debug,
        "perf": perf,
        "stability": stability_kickoff,
        "power": power,
        "app": app_lifecycle,
        "ota": ota,
        "test": run_test_suite,
    }.get(name)
    if fn is None:
        return BoardOpResult(name, False, f"unknown command {name!r}")
    return fn(*args, **kwargs)
