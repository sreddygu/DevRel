"""Collect a portable QLI device-health report as JSON.

Workflow: Device Health Agent.
The report includes operating-system, capacity, network, failed-service, audio,
camera, debugger, and QNN capability signals. Missing utilities are reported in
the result rather than installed or modified automatically.

Example::

    python3 qli_device_health_agent.py --output device_health.json
"""

import argparse
import json
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path


WORKFLOWS = ("Device Health Agent",)


def run_command(command: list[str]) -> dict:
    """Run a diagnostic command and return its exit code and captured output."""
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def existing_paths(pattern: str) -> list[str]:
    """Return sorted absolute paths matching a pattern below the root directory."""
    return sorted(str(path) for path in Path("/").glob(pattern))


def build_report() -> dict:
    """Build the complete device-health report without changing device state."""
    checks = {
        "os_release": run_command(["cat", "/etc/os-release"]),
        "uptime": run_command(["uptime"]),
        "memory": run_command(["free", "-h"]),
        "storage": run_command(["df", "-h", "/"]),
        "network": run_command(["ip", "-brief", "address"]),
        "failed_services": run_command(
            ["systemctl", "--failed", "--no-legend", "--plain"]
        ),
    }
    audio_devices = existing_paths("dev/snd/*")
    camera_devices = existing_paths("dev/video*")
    qnn_assets = existing_paths("opt/qnn/bin/*") + existing_paths("opt/qnn/lib/*")
    warnings = []
    failed_services = checks["failed_services"]["stdout"].splitlines()
    if failed_services:
        warnings.append(f"{len(failed_services)} failed systemd units")
    if not audio_devices:
        warnings.append("No ALSA devices detected")
    if not camera_devices:
        warnings.append("No V4L2 devices detected")
    if not qnn_assets:
        warnings.append("No QNN runtime assets detected")

    return {
        "agent": "QLI Device Health Agent",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
        "status": "WARN" if warnings else "PASS",
        "warnings": warnings,
        "capabilities": {
            "python3": shutil.which("python3"),
            "gdb": shutil.which("gdb"),
            "gdbserver": shutil.which("gdbserver"),
            "audio_device_count": len(audio_devices),
            "camera_device_count": len(camera_devices),
            "qnn_asset_count": len(qnn_assets),
        },
        "checks": checks,
    }


def main() -> None:
    """Optionally save the health report and print it as formatted JSON."""
    parser = argparse.ArgumentParser(description="Report QLI device health as JSON.")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--list-workflows", action="store_true")
    args = parser.parse_args()

    if args.list_workflows:
        print("\n".join(WORKFLOWS))
        return

    report_text = json.dumps(build_report(), indent=2)
    if args.output:
        args.output.write_text(report_text + "\n", encoding="utf-8")
    print(report_text)


if __name__ == "__main__":
    main()
