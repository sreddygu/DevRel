"""Run generic QLI device lifecycle and connectivity workflows.

This CLI covers identity, first boot, host validation, connectivity, recovery
discovery, flashing, version inspection, Wi-Fi configuration, SSH, and file
transfer. Flashing, recovery, roll-forward, and network reconfiguration are
plan-only unless ``--execute`` is explicitly supplied.

Requirements vary by subcommand and may include ``ssh``, ``scp``, ``nmcli``,
``fastboot``, ``adb``, or vendor flashing tools. Wi-Fi passwords should be read
from environment variables through ``--password-env`` and never stored here.

Examples::

    python3 qli_device_lifecycle_apps.py identity
    python3 qli_device_lifecycle_apps.py connectivity --host 192.0.2.10
"""

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path


WORKFLOWS = (
    "Device Identity Inspector",
    "First Boot Experience",
    "Host Environment Validation",
    "Device Connectivity Check",
    "Device Recovery Discovery",
    "Flash Latest QLI Build",
    "Verify Flash Succeeded",
    "Identify Installed Version",
    "Roll Forward from Old Image",
    "Recover Misconfigured Device",
    "Join New WiFi Network",
    "Switch WiFi Networks",
    "Configure Static IP",
    "SSH to Device",
    "Transfer File to Device",
)


def run_command(command: list[str], timeout: int = 120) -> dict:
    """Run a command with timeout handling and return a structured result."""
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except FileNotFoundError:
        return {"command": command, "returncode": 127, "stdout": "", "stderr": "command not found"}
    except subprocess.TimeoutExpired as error:
        return {
            "command": command,
            "returncode": 124,
            "stdout": (error.stdout or "").strip(),
            "stderr": "command timed out",
        }


def emit(workflow: str, result) -> None:
    """Print a timestamped workflow result as formatted JSON."""
    print(
        json.dumps(
            {
                "workflow": workflow,
                "captured_at_utc": datetime.now(timezone.utc).isoformat(),
                "result": result,
            },
            indent=2,
        )
    )


def device_identity() -> dict:
    """Collect local hostname, platform, operating-system, kernel, and CPU data."""
    return {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "os_release": run_command(["cat", "/etc/os-release"]),
        "kernel": run_command(["uname", "-a"]),
        "cpu": run_command(["sh", "-c", "lscpu 2>/dev/null || cat /proc/cpuinfo"]),
    }


def handle_identity(_args: argparse.Namespace) -> None:
    """Execute the Device Identity Inspector workflow."""
    emit("Device Identity Inspector", device_identity())


def handle_first_boot(_args: argparse.Namespace) -> None:
    """Summarize identity, uptime, boot warnings, and failed services."""
    emit(
        "First Boot Experience",
        {
            "identity": device_identity(),
            "uptime": run_command(["uptime"]),
            "boot_warnings": run_command(
                ["journalctl", "-b", "-p", "warning", "--no-pager", "-n", "100"]
            ),
            "failed_services": run_command(
                ["systemctl", "--failed", "--no-legend", "--plain"]
            ),
        },
    )


def handle_host_validation(args: argparse.Namespace) -> None:
    """Report whether required development tools are available on the host."""
    tools = {
        tool: shutil.which(tool)
        for tool in args.tools
    }
    emit(
        "Host Environment Validation",
        {
            "host": platform.platform(),
            "tools": tools,
            "missing": [tool for tool, path in tools.items() if not path],
        },
    )


def handle_connectivity(args: argparse.Namespace) -> None:
    """Test whether a TCP host and port can be reached within the timeout."""
    result = {"host": args.host, "port": args.port, "reachable": False}
    try:
        with socket.create_connection((args.host, args.port), timeout=args.timeout):
            result["reachable"] = True
    except OSError as error:
        result["error"] = str(error)
    emit("Device Connectivity Check", result)


def handle_recovery_discovery(_args: argparse.Namespace) -> None:
    """Discover common recovery utilities, USB devices, and block devices."""
    tools = ["fastboot", "adb", "qdl", "lsusb", "dfu-util", "uuu"]
    emit(
        "Device Recovery Discovery",
        {
            "tools": {tool: shutil.which(tool) for tool in tools},
            "usb": run_command(["lsusb"]),
            "block_devices": run_command(["lsblk", "-o", "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS"]),
        },
    )


def guarded_command(workflow: str, args: argparse.Namespace) -> None:
    """Plan or execute a potentially disruptive user-supplied command."""
    command = args.command
    if not command:
        raise SystemExit("A command is required after --command")
    if not args.execute:
        emit(workflow, {"status": "planned", "command": command, "execute": False})
        return
    emit(workflow, run_command(command, timeout=args.timeout))


def handle_verify_flash(_args: argparse.Namespace) -> None:
    """Collect read-only identity, root-filesystem, and service evidence after flashing."""
    emit(
        "Verify Flash Succeeded",
        {
            "identity": device_identity(),
            "root_filesystem": run_command(["findmnt", "/"]),
            "failed_services": run_command(
                ["systemctl", "--failed", "--no-legend", "--plain"]
            ),
        },
    )


def handle_installed_version(args: argparse.Namespace) -> None:
    """Read configured release files and list installed packages."""
    files = []
    for path_text in args.files:
        path = Path(path_text)
        if path.exists() and path.is_file():
            files.append({"path": str(path), "content": path.read_text(encoding="utf-8", errors="replace")})
    emit(
        "Identify Installed Version",
        {"files": files, "packages": run_command(["sh", "-c", args.package_command])},
    )


def require_execute(args: argparse.Namespace, workflow: str, command: list[str]) -> None:
    """Emit a plan unless execution was explicitly authorized by ``--execute``."""
    if not args.execute:
        emit(workflow, {"status": "planned", "command": command, "execute": False})
        return
    emit(workflow, run_command(command, timeout=args.timeout))


def handle_wifi_join(args: argparse.Namespace) -> None:
    """Plan or join a Wi-Fi network using ``nmcli`` and an environment password."""
    password = os.environ.get(args.password_env) if args.password_env else None
    command = ["nmcli", "device", "wifi", "connect", args.ssid]
    if password:
        command.extend(["password", password])
    safe_command = ["***" if value == password and password else value for value in command]
    if not args.execute:
        emit("Join New WiFi Network", {"status": "planned", "command": safe_command})
        return
    result = run_command(command, timeout=args.timeout)
    result["command"] = safe_command
    emit("Join New WiFi Network", result)


def handle_wifi_switch(args: argparse.Namespace) -> None:
    """Plan or activate an existing NetworkManager connection profile."""
    require_execute(
        args,
        "Switch WiFi Networks",
        ["nmcli", "connection", "up", args.connection],
    )


def handle_static_ip(args: argparse.Namespace) -> None:
    """Plan or configure a static IPv4 address with NetworkManager."""
    commands = [
        ["nmcli", "connection", "modify", args.connection, "ipv4.method", "manual"],
        ["nmcli", "connection", "modify", args.connection, "ipv4.addresses", args.address],
        ["nmcli", "connection", "modify", args.connection, "ipv4.gateway", args.gateway],
        ["nmcli", "connection", "modify", args.connection, "ipv4.dns", args.dns],
        ["nmcli", "connection", "up", args.connection],
    ]
    if not args.execute:
        emit("Configure Static IP", {"status": "planned", "commands": commands})
        return
    emit("Configure Static IP", [run_command(command, args.timeout) for command in commands])


def ssh_base(args: argparse.Namespace) -> list[str]:
    """Build the common SSH command prefix from remote connection arguments."""
    command = ["ssh", "-p", str(args.port)]
    if args.identity:
        command.extend(["-i", str(args.identity)])
    command.append(f"{args.user}@{args.host}")
    return command


def handle_ssh(args: argparse.Namespace) -> None:
    """Run a command on a remote device over SSH and emit the result."""
    command = ssh_base(args)
    command.extend(args.remote_command or ["uname", "-a"])
    emit("SSH to Device", run_command(command, timeout=args.timeout))


def handle_transfer(args: argparse.Namespace) -> None:
    """Copy one local file to a remote device with SCP."""
    command = ["scp", "-P", str(args.port)]
    if args.identity:
        command.extend(["-i", str(args.identity)])
    command.extend([str(args.source), f"{args.user}@{args.host}:{args.destination}"])
    emit("Transfer File to Device", run_command(command, timeout=args.timeout))


def add_guarded_parser(subparsers, name: str, workflow: str):
    """Add a plan-first subparser for a potentially destructive command."""
    parser = subparsers.add_parser(name, help=workflow)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--command", nargs=argparse.REMAINDER, required=True)
    parser.set_defaults(handler=lambda args: guarded_command(workflow, args))


def add_remote_arguments(parser: argparse.ArgumentParser) -> None:
    """Add shared SSH and SCP connection options to a subparser."""
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", default="root")
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--identity", type=Path)
    parser.add_argument("--timeout", type=int, default=120)


def build_parser() -> argparse.ArgumentParser:
    """Construct the lifecycle and connectivity command-line parser."""
    parser = argparse.ArgumentParser(description="Generic QLI device lifecycle and connectivity apps.")
    parser.add_argument("--list-workflows", action="store_true")
    subparsers = parser.add_subparsers(dest="app")

    identity = subparsers.add_parser("identity", help=WORKFLOWS[0])
    identity.set_defaults(handler=handle_identity)

    first_boot = subparsers.add_parser("first-boot", help=WORKFLOWS[1])
    first_boot.set_defaults(handler=handle_first_boot)

    host = subparsers.add_parser("host-validate", help=WORKFLOWS[2])
    host.add_argument("--tools", nargs="+", default=["ssh", "scp", "python3", "git"])
    host.set_defaults(handler=handle_host_validation)

    connectivity = subparsers.add_parser("connectivity", help=WORKFLOWS[3])
    connectivity.add_argument("--host", required=True)
    connectivity.add_argument("--port", type=int, default=22)
    connectivity.add_argument("--timeout", type=float, default=5)
    connectivity.set_defaults(handler=handle_connectivity)

    recovery = subparsers.add_parser("recovery-discovery", help=WORKFLOWS[4])
    recovery.set_defaults(handler=handle_recovery_discovery)

    add_guarded_parser(subparsers, "flash", WORKFLOWS[5])

    verify = subparsers.add_parser("verify-flash", help=WORKFLOWS[6])
    verify.set_defaults(handler=handle_verify_flash)

    version = subparsers.add_parser("installed-version", help=WORKFLOWS[7])
    version.add_argument(
        "--files",
        nargs="+",
        default=["/etc/qli-release", "/etc/os-release", "/etc/version"],
    )
    version.add_argument("--package-command", default="opkg list-installed 2>/dev/null || rpm -qa 2>/dev/null || true")
    version.set_defaults(handler=handle_installed_version)

    add_guarded_parser(subparsers, "roll-forward", WORKFLOWS[8])
    add_guarded_parser(subparsers, "recover", WORKFLOWS[9])

    wifi_join = subparsers.add_parser("wifi-join", help=WORKFLOWS[10])
    wifi_join.add_argument("--ssid", required=True)
    wifi_join.add_argument("--password-env")
    wifi_join.add_argument("--execute", action="store_true")
    wifi_join.add_argument("--timeout", type=int, default=60)
    wifi_join.set_defaults(handler=handle_wifi_join)

    wifi_switch = subparsers.add_parser("wifi-switch", help=WORKFLOWS[11])
    wifi_switch.add_argument("--connection", required=True)
    wifi_switch.add_argument("--execute", action="store_true")
    wifi_switch.add_argument("--timeout", type=int, default=60)
    wifi_switch.set_defaults(handler=handle_wifi_switch)

    static_ip = subparsers.add_parser("static-ip", help=WORKFLOWS[12])
    static_ip.add_argument("--connection", required=True)
    static_ip.add_argument("--address", required=True)
    static_ip.add_argument("--gateway", required=True)
    static_ip.add_argument("--dns", default="8.8.8.8")
    static_ip.add_argument("--execute", action="store_true")
    static_ip.add_argument("--timeout", type=int, default=60)
    static_ip.set_defaults(handler=handle_static_ip)

    ssh = subparsers.add_parser("ssh", help=WORKFLOWS[13])
    add_remote_arguments(ssh)
    ssh.add_argument("remote_command", nargs=argparse.REMAINDER)
    ssh.set_defaults(handler=handle_ssh)

    transfer = subparsers.add_parser("transfer", help=WORKFLOWS[14])
    add_remote_arguments(transfer)
    transfer.add_argument("--source", type=Path, required=True)
    transfer.add_argument("--destination", required=True)
    transfer.set_defaults(handler=handle_transfer)

    return parser


def main() -> None:
    """Dispatch the selected lifecycle workflow or print workflow discovery output."""
    parser = build_parser()
    args = parser.parse_args()
    if args.list_workflows:
        print("\n".join(WORKFLOWS))
        return
    if not hasattr(args, "handler"):
        parser.print_help()
        raise SystemExit(2)
    args.handler(args)


if __name__ == "__main__":
    main()
