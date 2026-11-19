"""Run generic QLI debugging, diagnostics, and deployment workflows.

Debugger workflows invoke local ``gdb`` or ``gdbserver`` with a user-supplied
program. Log diagnostics are read-only. Remote deployment uses ``scp`` and
``ssh`` and remains plan-only unless ``--execute`` is explicitly supplied.

Only debug programs that are safe to stop, continue, or crash. Review target
addresses and remote paths before executing deployment against a device.

Examples::

    python3 qli_debug_deploy_apps.py logs --priority warning
    python3 qli_debug_deploy_apps.py clean-build
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


WORKFLOWS = (
    "Remote Debug Hello World",
    "Breakpoint Validation",
    "Crash Investigation",
    "Log Based Diagnostics",
    "Deploy Hello World",
    "Deploy Updated Build",
    "Deploy to Second Device",
    "Clean Build Deploy Verify",
)


def emit(workflow: str, result) -> None:
    """Print a workflow result as formatted JSON."""
    print(json.dumps({"workflow": workflow, "result": result}, indent=2))


def run_command(command: list[str], timeout: int = 300, cwd: Path | None = None) -> dict:
    """Run a debugger or deployment command and return a structured result."""
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
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
    except subprocess.TimeoutExpired:
        return {"command": command, "returncode": 124, "stdout": "", "stderr": "command timed out"}


def handle_remote_debug(args: argparse.Namespace) -> None:
    """Describe or launch a ``gdbserver`` remote-debug session."""
    server_command = ["gdbserver", f"{args.listen_host}:{args.port}", *args.program]
    client_commands = [
        f"target remote {args.target_host}:{args.port}",
        "continue",
        "quit",
    ]
    result = {"server_command": server_command, "client_commands": client_commands}
    if args.execute_server:
        result["server"] = run_command(server_command, args.timeout)
    emit("Remote Debug Hello World", result)


def handle_breakpoint(args: argparse.Namespace) -> None:
    """Run a program under GDB, stop at a breakpoint, and capture a backtrace."""
    command = ["gdb", "-q", "-batch", "-ex", f"break {args.breakpoint}", "-ex", "run", "-ex", "bt", "--args", *args.program]
    emit("Breakpoint Validation", run_command(command, args.timeout))


def handle_crash(args: argparse.Namespace) -> None:
    """Run a program under GDB and collect a full backtrace after failure."""
    command = ["gdb", "-q", "-batch", "-ex", "run", "-ex", "bt full", "--args", *args.program]
    emit("Crash Investigation", run_command(command, args.timeout))


def handle_logs(args: argparse.Namespace) -> None:
    """Collect failed services, priority-filtered journal entries, and kernel warnings."""
    emit(
        "Log Based Diagnostics",
        {
            "failed_services": run_command(["systemctl", "--failed", "--no-legend", "--plain"]),
            "journal": run_command(
                ["journalctl", "-b", "-p", args.priority, "--no-pager", "-n", str(args.lines)]
            ),
            "kernel": run_command(["dmesg", "--level", "err,warn"]),
        },
    )


def remote_parts(args: argparse.Namespace) -> tuple[list[str], list[str]]:
    """Build shared SSH and SCP command prefixes for a remote target."""
    ssh = ["ssh", "-p", str(args.port)]
    scp = ["scp", "-P", str(args.port)]
    if args.identity:
        ssh.extend(["-i", str(args.identity)])
        scp.extend(["-i", str(args.identity)])
    target = f"{args.user}@{args.host}"
    ssh.append(target)
    return ssh, scp


def deploy_file(args: argparse.Namespace, workflow: str) -> None:
    """Plan or execute file copy and optional remote execution for a deployment."""
    ssh, scp = remote_parts(args)
    copy_command = [*scp, str(args.source), f"{args.user}@{args.host}:{args.destination}"]
    run_remote = [*ssh, *args.remote_command] if args.remote_command else None
    if not args.execute:
        emit(
            workflow,
            {"status": "planned", "copy_command": copy_command, "remote_command": run_remote},
        )
        return
    copy_result = run_command(copy_command, args.timeout)
    remote_result = None
    if copy_result["returncode"] == 0 and run_remote:
        remote_result = run_command(run_remote, args.timeout)
    emit(workflow, {"copy": copy_result, "remote": remote_result})


def handle_clean_build(args: argparse.Namespace) -> None:
    """Create, syntax-check, run, update, and clean a temporary Python project."""
    with tempfile.TemporaryDirectory(prefix="qli_clean_build_") as temporary_directory:
        workdir = Path(temporary_directory)
        source = workdir / "hello.py"
        source.write_text(
            "import argparse\n\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--message', default='Hello from QLI')\n"
            "args = parser.parse_args()\n"
            "print(args.message)\n",
            encoding="utf-8",
        )
        syntax = run_command(
            [
                sys.executable,
                "-c",
                "compile(open('hello.py', encoding='utf-8').read(), 'hello.py', 'exec')",
            ],
            cwd=workdir,
        )
        first = run_command([sys.executable, "hello.py"], cwd=workdir)
        updated = run_command(
            [sys.executable, "hello.py", "--message", args.updated_message],
            cwd=workdir,
        )
        emit(
            "Clean Build Deploy Verify",
            {"syntax": syntax, "initial_run": first, "updated_run": updated, "cleaned": True},
        )


def add_program_arguments(parser: argparse.ArgumentParser) -> None:
    """Add timeout and remainder-style program arguments to a debugger command."""
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("program", nargs=argparse.REMAINDER)


def add_deploy_arguments(parser: argparse.ArgumentParser) -> None:
    """Add shared remote target, source, destination, and execution options."""
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", default="root")
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--identity", type=Path)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--remote-command", nargs=argparse.REMAINDER)


def build_parser() -> argparse.ArgumentParser:
    """Construct the debugging and deployment command-line parser."""
    parser = argparse.ArgumentParser(description="Generic QLI debugging and deployment apps.")
    parser.add_argument("--list-workflows", action="store_true")
    subparsers = parser.add_subparsers(dest="app")

    remote_debug = subparsers.add_parser("remote-debug", help=WORKFLOWS[0])
    remote_debug.add_argument("--listen-host", default="0.0.0.0")
    remote_debug.add_argument("--target-host", default="127.0.0.1")
    remote_debug.add_argument("--port", type=int, default=2345)
    remote_debug.add_argument("--execute-server", action="store_true")
    add_program_arguments(remote_debug)
    remote_debug.set_defaults(handler=handle_remote_debug)

    breakpoint = subparsers.add_parser("breakpoint", help=WORKFLOWS[1])
    breakpoint.add_argument("--breakpoint", default="main")
    add_program_arguments(breakpoint)
    breakpoint.set_defaults(handler=handle_breakpoint)

    crash = subparsers.add_parser("crash", help=WORKFLOWS[2])
    add_program_arguments(crash)
    crash.set_defaults(handler=handle_crash)

    logs = subparsers.add_parser("logs", help=WORKFLOWS[3])
    logs.add_argument("--priority", default="warning")
    logs.add_argument("--lines", type=int, default=200)
    logs.set_defaults(handler=handle_logs)

    deploy_hello = subparsers.add_parser("deploy-hello", help=WORKFLOWS[4])
    add_deploy_arguments(deploy_hello)
    deploy_hello.set_defaults(handler=lambda args: deploy_file(args, WORKFLOWS[4]))

    deploy_updated = subparsers.add_parser("deploy-updated", help=WORKFLOWS[5])
    add_deploy_arguments(deploy_updated)
    deploy_updated.set_defaults(handler=lambda args: deploy_file(args, WORKFLOWS[5]))

    deploy_second = subparsers.add_parser("deploy-second", help=WORKFLOWS[6])
    add_deploy_arguments(deploy_second)
    deploy_second.set_defaults(handler=lambda args: deploy_file(args, WORKFLOWS[6]))

    clean = subparsers.add_parser("clean-build", help=WORKFLOWS[7])
    clean.add_argument("--updated-message", default="Updated hello from QLI")
    clean.set_defaults(handler=handle_clean_build)

    return parser


def main() -> None:
    """Dispatch the selected debug or deployment workflow."""
    parser = build_parser()
    args = parser.parse_args()
    if args.list_workflows:
        print("\n".join(WORKFLOWS))
        return
    if not hasattr(args, "handler"):
        parser.print_help()
        raise SystemExit(2)
    if hasattr(args, "program") and not args.program:
        raise SystemExit("A program is required")
    args.handler(args)


if __name__ == "__main__":
    main()
