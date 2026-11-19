"""Run non-destructive QLI device validation over PuTTY SSH tools.

The runner collects device, network, toolchain, multimedia, AI-runtime, package,
and journal evidence. Temporary transfer and deployment probes are removed from
the target after validation.
"""

import argparse
import getpass
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


SAFE_CHECKS = {
    "identity": "hostname; uname -a; cat /etc/os-release; cat /etc/hostname",
    "build_metadata": (
        "for f in /etc/*release /etc/*version /etc/build* /etc/os-release; do "
        "[ -f \"$f\" ] && echo ===$f=== && cat \"$f\"; done 2>/dev/null"
    ),
    "network": (
        "ip -brief address; ip route; "
        "command -v nmcli >/dev/null && "
        "nmcli -t -f DEVICE,TYPE,STATE device status || true"
    ),
    "system_health": (
        "uptime; free -h; df -h; df -i; "
        "systemctl --failed --no-legend 2>/dev/null || true"
    ),
    "toolchain": (
        "for c in python3 gcc g++ cmake make git gdb gdbserver docker podman; do "
        "printf '%s=' \"$c\"; command -v \"$c\" || true; done"
    ),
    "audio": (
        "ls -la /dev/snd 2>/dev/null || true; "
        "command -v aplay >/dev/null && aplay -l || true; "
        "command -v arecord >/dev/null && arecord -l || true"
    ),
    "camera": (
        "ls -la /dev/video* 2>/dev/null || true; "
        "command -v v4l2-ctl >/dev/null && v4l2-ctl --list-devices || true; "
        "command -v media-ctl >/dev/null && media-ctl -p 2>/dev/null | head -120 || true"
    ),
    "ai_runtime": (
        "find /opt /usr -maxdepth 4 -type f "
        "\\( -iname '*qnn*' -o -iname '*snpe*' -o -iname '*genie*' "
        "-o -iname '*onnxruntime*' -o -iname '*tflite*' \\) 2>/dev/null | head -200"
    ),
    "samples": (
        "find /opt /usr/share /home /root -maxdepth 4 -type d "
        "\\( -iname '*sample*' -o -iname '*example*' -o -iname '*demo*' \\) "
        "2>/dev/null | head -200"
    ),
    "packages": (
        "if command -v rpm >/dev/null; then rpm -qa | sort | head -300; "
        "elif command -v opkg >/dev/null; then opkg list-installed | head -300; "
        "elif command -v dpkg-query >/dev/null; then dpkg-query -W | head -300; fi"
    ),
    "recent_errors": (
        "journalctl -p warning..alert -b --no-pager -n 120 2>/dev/null || true"
    ),
}


def run_process(command: list[str], timeout: int) -> dict:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=timeout,
        check=False,
    )
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def plink_command(args: argparse.Namespace, password: str, remote_command: str) -> list[str]:
    command = [
        str(args.plink),
        "-ssh",
        "-batch",
    ]
    if args.hostkey:
        command.extend(["-hostkey", args.hostkey])
    command.extend([f"{args.user}@{args.host}", "-pw", password, remote_command])
    return command


def run_remote(
    args: argparse.Namespace, password: str, remote_command: str, timeout: int = 90
) -> dict:
    return run_process(plink_command(args, password, remote_command), timeout)


def transfer_probe(args: argparse.Namespace, password: str) -> dict:
    content = f"QLI transfer probe {datetime.now(timezone.utc).isoformat()}\n".encode(
        "utf-8"
    )
    expected_hash = hashlib.sha256(content).hexdigest()
    remote_path = "/tmp/qli_transfer_probe.txt"
    with tempfile.TemporaryDirectory() as temp_dir:
        local_path = Path(temp_dir) / "qli_transfer_probe.txt"
        local_path.write_bytes(content)
        copy_command = [str(args.pscp), "-batch"]
        if args.hostkey:
            copy_command.extend(["-hostkey", args.hostkey])
        copy_command.extend(
            [
                "-pw",
                password,
                str(local_path),
                f"{args.user}@{args.host}:{remote_path}",
            ]
        )
        copy_result = run_process(copy_command, 90)
    verify_result = run_remote(
        args,
        password,
        f"sha256sum {remote_path}; wc -c {remote_path}; rm -f {remote_path}",
    )
    return {
        "expected_sha256": expected_hash,
        "copy": copy_result,
        "verify_and_cleanup": verify_result,
    }


def deployment_probe(args: argparse.Namespace, password: str) -> dict:
    initial_message = f"Hello from QLI 2.0 on {args.device_label}"
    updated_message = f"Updated hello from QLI 2.0 on {args.device_label}"
    remote_command = f"""
set -eu
work=/tmp/qli_deploy_probe
rm -rf "$work"
mkdir -p "$work"
cat > "$work/hello.py" <<'PY'
from pathlib import Path
message = {initial_message!r}
Path("/tmp/qli_deploy_probe/run.log").write_text(message + "\\n", encoding="utf-8")
print(message)
PY
python3 "$work/hello.py"
python3 - <<'PY'
from pathlib import Path
path = Path("/tmp/qli_deploy_probe/hello.py")
path.write_text(
    path.read_text(encoding="utf-8").replace({initial_message!r}, {updated_message!r}),
    encoding="utf-8",
)
PY
python3 "$work/hello.py"
cat "$work/run.log"
python3 -c 'compile(open("/tmp/qli_deploy_probe/hello.py", encoding="utf-8").read(), "hello.py", "exec")'
rm -rf "$work"
""".strip()
    return run_remote(args, password, remote_command)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run non-destructive QLI 2.0 device dogfooding checks over SSH."
    )
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", default="root")
    parser.add_argument("--device-label", default="QLI device")
    parser.add_argument("--hostkey")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--plink", type=Path, default=Path(r"C:\Program Files\PuTTY\plink.exe")
    )
    parser.add_argument(
        "--pscp", type=Path, default=Path(r"C:\Program Files\PuTTY\pscp.exe")
    )
    args = parser.parse_args()

    password = os.environ.get("QLI_SSH_PASSWORD") or getpass.getpass("SSH password: ")
    report = {
        "host": args.host,
        "user": args.user,
        "device_label": args.device_label,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "checks": {},
    }
    for name, remote_command in SAFE_CHECKS.items():
        report["checks"][name] = run_remote(args, password, remote_command)
    report["checks"]["file_transfer"] = transfer_probe(args, password)
    report["checks"]["deployment"] = deployment_probe(args, password)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
