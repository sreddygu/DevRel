"""Inspect, configure, verify, and restore persistent QLI IPv4 settings.

This device-side CLI implements the ``Configure Static IP`` dogfooding workflow
with NetworkManager. It discovers the active connection, derives a candidate
address from the current subnet, performs a best-effort conflict probe, and
prints a dry-run plan by default.

Network changes require ``--execute``. Activating a modified connection requires
the additional ``--activate`` flag because cycling a remotely managed interface
can terminate SSH and may make the device unreachable. Prefer a serial console,
local terminal, reserved address, and documented rollback plan for live changes.

Examples::

    python3 qli_network_apps.py inspect --interface wlp1s0
    python3 qli_network_apps.py configure-static --interface wlp1s0 --host-number 250
    python3 qli_network_apps.py configure-static --interface wlp1s0 --host-number 250 --execute
    python3 qli_network_apps.py configure-static --interface wlp1s0 --host-number 250 --execute --activate
    python3 qli_network_apps.py verify --interface wlp1s0 --expected-address 192.168.29.250/24
    python3 qli_network_apps.py restore-dhcp --interface wlp1s0 --execute --activate
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKFLOWS = ("Configure Static IP",)


def run_command(command: list[str], timeout: int = 30) -> dict[str, Any]:
    """Run one command and return its arguments, output, and return code."""
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


def emit(result: Any) -> None:
    """Print a timestamped Configure Static IP workflow result as JSON."""
    print(
        json.dumps(
            {
                "workflow": WORKFLOWS[0],
                "captured_at_utc": datetime.now(timezone.utc).isoformat(),
                "result": result,
            },
            indent=2,
        )
    )


def require_command(name: str) -> None:
    """Exit with a clear message when a required device utility is unavailable."""
    if shutil.which(name) is None:
        raise SystemExit(f"error: required command not found: {name}")


def command_stdout(command: list[str], timeout: int = 30) -> str:
    """Return stdout from a successful command or raise a descriptive error."""
    result = run_command(command, timeout)
    if result["returncode"] != 0:
        detail = result["stderr"] or result["stdout"] or f"exit code {result['returncode']}"
        raise SystemExit(f"error: {' '.join(command)}: {detail}")
    return str(result["stdout"])


def discover_connection(interface: str, connection: str | None) -> str:
    """Return the requested or currently active NetworkManager connection name."""
    if connection:
        return connection
    output = command_stdout(["nmcli", "-g", "GENERAL.CONNECTION", "device", "show", interface])
    name = output.splitlines()[0].strip() if output else ""
    if not name or name == "--":
        raise SystemExit(f"error: no active NetworkManager connection found on {interface}")
    return name


def live_address(interface: str) -> ipaddress.IPv4Interface:
    """Return the first live global IPv4 address assigned to an interface."""
    output = command_stdout(["ip", "-o", "-4", "address", "show", "dev", interface, "scope", "global"])
    for line in output.splitlines():
        fields = line.split()
        if "inet" in fields:
            return ipaddress.IPv4Interface(fields[fields.index("inet") + 1])
    raise SystemExit(f"error: no global IPv4 address found on {interface}")


def default_gateway(interface: str) -> ipaddress.IPv4Address:
    """Return the IPv4 default gateway routed through an interface."""
    output = command_stdout(["ip", "-4", "route", "show", "default", "dev", interface])
    fields = output.split()
    if "via" not in fields:
        raise SystemExit(f"error: no IPv4 default gateway found on {interface}")
    return ipaddress.IPv4Address(fields[fields.index("via") + 1])


def profile_settings(connection: str) -> dict[str, str]:
    """Read persistent IPv4 fields from a NetworkManager connection profile."""
    fields = (
        "connection.id",
        "connection.uuid",
        "connection.autoconnect",
        "ipv4.method",
        "ipv4.addresses",
        "ipv4.gateway",
        "ipv4.dns",
        "ipv4.ignore-auto-dns",
    )
    output = command_stdout(["nmcli", "-g", ",".join(fields), "connection", "show", connection])
    values = output.splitlines()
    values.extend([""] * (len(fields) - len(values)))
    return dict(zip(fields, values, strict=True))


def inspect_network(interface: str, connection: str | None) -> dict[str, Any]:
    """Collect live and persistent IPv4 state without changing the device."""
    connection_name = discover_connection(interface, connection)
    address = live_address(interface)
    gateway = default_gateway(interface)
    return {
        "interface": interface,
        "connection": connection_name,
        "live_address": str(address),
        "network": str(address.network),
        "gateway": str(gateway),
        "profile": profile_settings(connection_name),
        "address_details": run_command(["ip", "-4", "address", "show", "dev", interface]),
        "route_details": run_command(["ip", "-4", "route", "show"]),
    }


def candidate_address(
    current: ipaddress.IPv4Interface,
    address: str | None,
    host_number: int | None,
) -> ipaddress.IPv4Interface:
    """Validate an explicit CIDR address or derive one from the current subnet."""
    if address:
        value = address if "/" in address else f"{address}/{current.network.prefixlen}"
        candidate = ipaddress.IPv4Interface(value)
    else:
        if host_number is None:
            raise SystemExit("error: provide --address or --host-number")
        candidate_ip = ipaddress.IPv4Address(int(current.network.network_address) + host_number)
        candidate = ipaddress.IPv4Interface(f"{candidate_ip}/{current.network.prefixlen}")
    if candidate.ip not in current.network:
        raise SystemExit(f"error: candidate {candidate} is outside current network {current.network}")
    if candidate.ip in (current.network.network_address, current.network.broadcast_address):
        raise SystemExit(f"error: candidate {candidate.ip} is a reserved network address")
    return candidate


def validate_dns(values: list[str]) -> list[str]:
    """Validate DNS arguments as IPv4 addresses and return normalized strings."""
    return [str(ipaddress.IPv4Address(value)) for value in values]


def conflict_probe(
    address: ipaddress.IPv4Address,
    current: ipaddress.IPv4Address,
    timeout: int,
) -> dict[str, Any]:
    """Perform a best-effort ping probe and flag a responding candidate address."""
    if address == current:
        return {"status": "conflict", "reason": "candidate is the current device address"}
    probe = run_command(["ping", "-c", "2", "-W", "1", str(address)], timeout)
    return {
        "status": "conflict" if probe["returncode"] == 0 else "no-ping-response",
        "warning": "No ping response does not prove an address is unassigned; reserve it in DHCP or confirm with the network administrator.",
        "probe": probe,
    }


def write_backup(path: Path, state: dict[str, Any]) -> None:
    """Write pre-change network evidence to a user-selected JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def handle_inspect(args: argparse.Namespace) -> None:
    """Emit the current live address, route, and persistent profile."""
    emit(inspect_network(args.interface, args.connection))


def handle_configure_static(args: argparse.Namespace) -> None:
    """Plan or persist a manual IPv4 profile and optionally activate it."""
    state = inspect_network(args.interface, args.connection)
    current = ipaddress.IPv4Interface(state["live_address"])
    connection = str(state["connection"])
    candidate = candidate_address(current, args.address, args.host_number)
    gateway = ipaddress.IPv4Address(args.gateway) if args.gateway else ipaddress.IPv4Address(state["gateway"])
    if gateway not in candidate.network:
        raise SystemExit(f"error: gateway {gateway} is outside candidate network {candidate.network}")
    dns = validate_dns(args.dns)
    probe = conflict_probe(candidate.ip, current.ip, args.timeout)
    if probe["status"] == "conflict" and not args.allow_conflict:
        emit({"status": "blocked", "reason": "candidate address conflict", "candidate": str(candidate), "probe": probe})
        raise SystemExit(2)
    modify = [
        "nmcli",
        "connection",
        "modify",
        connection,
        "ipv4.method",
        "manual",
        "ipv4.addresses",
        str(candidate),
        "ipv4.gateway",
        str(gateway),
        "ipv4.dns",
        " ".join(dns),
        "ipv4.ignore-auto-dns",
        "yes",
    ]
    activate = ["nmcli", "connection", "up", connection, "ifname", args.interface]
    plan = {
        "status": "planned" if not args.execute else "executing",
        "interface": args.interface,
        "connection": connection,
        "current_address": str(current),
        "candidate_address": str(candidate),
        "gateway": str(gateway),
        "dns": dns,
        "conflict_probe": probe,
        "commands": [modify] + ([activate] if args.activate else []),
        "activation_warning": "Activating may terminate SSH. Use a serial/local console and reserve the address before activation.",
    }
    if not args.execute:
        emit(plan)
        return
    if args.backup:
        write_backup(args.backup, state)
    results = [run_command(modify, args.timeout)]
    if results[0]["returncode"] == 0 and args.activate:
        results.append(run_command(activate, args.timeout))
    emit(
        {
            **plan,
            "status": "completed" if all(result["returncode"] == 0 for result in results) else "failed",
            "results": results,
            "persistent_profile": profile_settings(connection),
        }
    )


def handle_verify(args: argparse.Namespace) -> None:
    """Verify persistent manual settings and optionally the active address."""
    state = inspect_network(args.interface, args.connection)
    profile = state["profile"]
    expected = ipaddress.IPv4Interface(args.expected_address) if args.expected_address else None
    live = ipaddress.IPv4Interface(state["live_address"])
    profile_addresses = [value for value in str(profile["ipv4.addresses"]).split(",") if value]
    checks = {
        "profile_is_manual": profile["ipv4.method"] == "manual",
        "profile_has_address": bool(profile_addresses),
        "live_matches_expected": expected is None or live == expected,
        "profile_matches_expected": expected is None or str(expected) in profile_addresses,
    }
    emit({"status": "passed" if all(checks.values()) else "failed", "checks": checks, "state": state})


def handle_restore_dhcp(args: argparse.Namespace) -> None:
    """Plan or restore automatic DHCP settings and optionally activate them."""
    state = inspect_network(args.interface, args.connection)
    connection = str(state["connection"])
    modify = [
        "nmcli",
        "connection",
        "modify",
        connection,
        "ipv4.method",
        "auto",
        "ipv4.addresses",
        "",
        "ipv4.gateway",
        "",
        "ipv4.dns",
        "",
        "ipv4.ignore-auto-dns",
        "no",
    ]
    activate = ["nmcli", "connection", "up", connection, "ifname", args.interface]
    plan = {
        "status": "planned" if not args.execute else "executing",
        "interface": args.interface,
        "connection": connection,
        "commands": [modify] + ([activate] if args.activate else []),
    }
    if not args.execute:
        emit(plan)
        return
    if args.backup:
        write_backup(args.backup, state)
    results = [run_command(modify, args.timeout)]
    if results[0]["returncode"] == 0 and args.activate:
        results.append(run_command(activate, args.timeout))
    emit(
        {
            **plan,
            "status": "completed" if all(result["returncode"] == 0 for result in results) else "failed",
            "results": results,
            "persistent_profile": profile_settings(connection),
        }
    )


def add_common_network_arguments(parser: argparse.ArgumentParser) -> None:
    """Add interface, connection, and timeout arguments shared by commands."""
    parser.add_argument("--interface", default="wlp1s0", help="Network interface to inspect or configure.")
    parser.add_argument("--connection", help="NetworkManager connection name; defaults to the active profile.")
    parser.add_argument("--timeout", type=int, default=30, help="Per-command timeout in seconds.")


def build_parser() -> argparse.ArgumentParser:
    """Build and return the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-workflows", action="store_true", help="List covered dogfooding workflows and exit.")
    subparsers = parser.add_subparsers(dest="command")

    inspect_parser = subparsers.add_parser("inspect", help="Inspect current DHCP/static state without changes.")
    add_common_network_arguments(inspect_parser)
    inspect_parser.set_defaults(handler=handle_inspect)

    configure = subparsers.add_parser("configure-static", help="Plan or configure a persistent static IPv4 address.")
    add_common_network_arguments(configure)
    candidate = configure.add_mutually_exclusive_group(required=True)
    candidate.add_argument("--address", help="Static IPv4 address, with optional CIDR prefix.")
    candidate.add_argument("--host-number", type=int, help="Host number within the current IPv4 subnet.")
    configure.add_argument("--gateway", help="IPv4 gateway; defaults to the current default gateway.")
    configure.add_argument("--dns", nargs="+", default=["8.8.8.8", "8.8.4.4"], help="One or more DNS IPv4 addresses.")
    configure.add_argument("--allow-conflict", action="store_true", help="Continue even when the candidate responds to ping.")
    configure.add_argument("--execute", action="store_true", help="Persist profile changes; default is dry-run.")
    configure.add_argument("--activate", action="store_true", help="Activate the profile; may terminate SSH.")
    configure.add_argument("--backup", type=Path, help="Write pre-change evidence to this JSON path.")
    configure.set_defaults(handler=handle_configure_static)

    verify = subparsers.add_parser("verify", help="Verify persistent and live static IPv4 settings.")
    add_common_network_arguments(verify)
    verify.add_argument("--expected-address", help="Expected active/profile CIDR address.")
    verify.set_defaults(handler=handle_verify)

    restore = subparsers.add_parser("restore-dhcp", help="Plan or restore automatic DHCP settings.")
    add_common_network_arguments(restore)
    restore.add_argument("--execute", action="store_true", help="Persist DHCP settings; default is dry-run.")
    restore.add_argument("--activate", action="store_true", help="Activate the DHCP profile; may terminate SSH.")
    restore.add_argument("--backup", type=Path, help="Write pre-change evidence to this JSON path.")
    restore.set_defaults(handler=handle_restore_dhcp)

    return parser


def main() -> None:
    """Parse arguments and execute the selected network workflow."""
    parser = build_parser()
    args = parser.parse_args()
    if args.list_workflows:
        print("\n".join(WORKFLOWS))
        return
    if not getattr(args, "handler", None):
        parser.print_help()
        return
    require_command("nmcli")
    require_command("ip")
    require_command("ping")
    if getattr(args, "activate", False) and not getattr(args, "execute", False):
        raise SystemExit("error: --activate requires --execute")
    args.handler(args)


if __name__ == "__main__":
    main()
