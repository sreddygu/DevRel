"""Standalone lightweight CLI for the QUAD MCP client.

Exposed as the ``quad-client`` entry point. Has only two third-party
dependencies (``typer`` + ``httpx``), so a pure client-side install via
``pip install quad-mcp-client`` has minimal footprint.

Commands:
    quad-client install        # interactive provisioning + connection test
    quad-client status         # what's installed
    quad-client preview        # print settings.json that install would write
    quad-client uninstall      # remove bundled skills
    quad-client connect-test   # verify a transport without writing files

See also:
    install.sh                  # interactive client-machine setup
    docs/INSTALL.md             # walkthrough of the manual flow
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from quad_mcp_client import get_provisioner
from quad_mcp_client.claude_code import ClaudeCodeProvisioner
from quad_mcp_client.claude_code.provisioner import TransportConfig
from quad_mcp_client.connection import probe
from quad_mcp_client.opencode import OpenCodeProvisioner

app = typer.Typer(
    name="quad-client",
    help=(
        "Lightweight QUAD MCP client provisioner. Configures Claude Code "
        "(or another MCP-compatible IDE) to talk to a QUAD MCP server. "
        "The MCP server itself can run locally, on a remote machine over SSH, "
        "or as a hosted HTTP/SSE service — see `quad-client install --help`."
    ),
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)


# --- install ---------------------------------------------------------------


@app.command()
def install(
    transport: str = typer.Option(
        "stdio-local",
        help="MCP transport: 'stdio-local' | 'stdio-ssh' | 'sse-http'",
    ),
    # stdio-local
    server_command: str = typer.Option("python", help="(stdio-local) command to spawn the server"),
    adapter_mode: str = typer.Option("mock", help="(stdio-local) adapter mode for the server"),
    # stdio-ssh
    ssh_user: str = typer.Option("", help="(stdio-ssh) remote SSH username"),
    ssh_host: str = typer.Option("", help="(stdio-ssh) remote SSH hostname / IP"),
    ssh_port: int = typer.Option(22, help="(stdio-ssh) SSH port"),
    ssh_key: str | None = typer.Option(None, help="(stdio-ssh) path to private key"),
    ssh_server_command: str = typer.Option(
        "python -m quad.mcp.server", help="(stdio-ssh) command run on the remote machine"
    ),
    # sse-http
    sse_url: str = typer.Option("", help="(sse-http) full URL to the MCP SSE endpoint"),
    sse_auth_token_env: str | None = typer.Option(
        None, help="(sse-http) name of env var holding the bearer token"
    ),
    # common
    client: str = typer.Option(
        "claude_code", help="Which IDE/agent client to provision: 'claude_code' | 'opencode'"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing config"),
    skip_test: bool = typer.Option(False, help="Skip the connection test"),
    project_root: str | None = typer.Option(
        None, help="Project root (default: cwd). The .claude/ dir is created here."
    ),
) -> None:
    """Provision Claude Code (or another MCP client) to talk to the QUAD server."""
    root = Path(project_root) if project_root else Path.cwd()

    if transport == "stdio-local":
        cfg = TransportConfig(
            transport="stdio-local",
            server_command=server_command,
            adapter_mode=adapter_mode,
        )
        probe_kwargs: dict[str, Any] = {"command": server_command}
    elif transport == "stdio-ssh":
        if not ssh_host or not ssh_user:
            typer.echo("Error: stdio-ssh requires --ssh-user and --ssh-host", err=True)
            raise typer.Exit(code=2)
        cfg = TransportConfig(
            transport="stdio-ssh",
            ssh_user=ssh_user,
            ssh_host=ssh_host,
            ssh_port=ssh_port,
            ssh_key=ssh_key,
            ssh_server_command=ssh_server_command,
        )
        probe_kwargs = {
            "ssh_user": ssh_user,
            "ssh_host": ssh_host,
            "ssh_port": ssh_port,
            "ssh_key": ssh_key,
            "server_command": ssh_server_command,
        }
    elif transport == "sse-http":
        if not sse_url:
            typer.echo("Error: sse-http requires --sse-url", err=True)
            raise typer.Exit(code=2)
        cfg = TransportConfig(
            transport="sse-http",
            sse_url=sse_url,
            sse_auth_token_env=sse_auth_token_env,
        )
        probe_kwargs = {"url": sse_url}
    else:
        typer.echo(f"Error: unknown transport {transport!r}", err=True)
        typer.echo("Valid choices: stdio-local, stdio-ssh, sse-http", err=True)
        raise typer.Exit(code=2)

    # Connection test
    if not skip_test:
        typer.echo(f"Testing {transport} connection…")
        result = probe(transport, **probe_kwargs)  # type: ignore[arg-type]
        typer.echo(result.render())
        if not result.ok:
            if not force:
                typer.echo(
                    "\nConnection test failed. Re-run with --force to provision anyway, "
                    "or fix the issue above and retry.",
                    err=True,
                )
                raise typer.Exit(code=1)
            typer.echo("--force given; provisioning anyway despite failed connection test.")

    # Provision
    try:
        prov = get_provisioner(client)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2) from None

    if isinstance(prov, (ClaudeCodeProvisioner, OpenCodeProvisioner)):
        outcome = prov.install(root, force=force, transport_config=cfg)
    else:
        outcome = prov.install(root, force=force)

    typer.echo("")
    typer.echo(f"Provisioned {outcome.client}:")
    typer.echo(f"  settings.json: {outcome.settings_path}")
    typer.echo(f"  skills dir:    {outcome.skills_dir}")
    typer.echo(f"  written:       {len(outcome.files_written)} file(s)")
    if outcome.files_skipped:
        typer.echo(
            f"  skipped:       {len(outcome.files_skipped)} file(s) — use --force to overwrite"
        )
    for note in outcome.notes:
        typer.echo(f"  note: {note}")
    typer.echo("")
    agent_label = "opencode" if client == "opencode" else "Claude Code"
    typer.echo(
        f"Next: open {agent_label} in this project. The QUAD MCP tools will appear in the tool list."
    )


# --- status ----------------------------------------------------------------


@app.command()
def status(
    client: str = typer.Option("claude_code", help="Which IDE/agent client to check"),
    project_root: str | None = typer.Option(None, help="Project root (default: cwd)"),
) -> None:
    """Show what's currently installed."""
    root = Path(project_root) if project_root else Path.cwd()
    try:
        prov = get_provisioner(client)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2) from None
    s = prov.status(root)
    typer.echo(f"Client:           {s['client']}")
    typer.echo(
        f"settings.json:    "
        f"{'present' if s['settings_exists'] else 'missing'} @ {s['settings_path']}"
    )
    typer.echo(
        f"Skills dir:       "
        f"{'present' if s['skills_dir_exists'] else 'missing'} @ {s['skills_dir']}"
    )
    typer.echo(f"Bundled skills:   {s['bundled_skill_count']}")
    typer.echo(f"Installed skills: {s['installed_skill_count']}")
    if s["missing_skills"]:
        typer.echo(f"Missing:          {', '.join(s['missing_skills'])}")
    if s["extra_user_skills"]:
        typer.echo(f"User-added:       {', '.join(s['extra_user_skills'])}")


# --- preview ---------------------------------------------------------------


@app.command()
def preview(
    transport: str = typer.Option("stdio-local"),
    adapter_mode: str = typer.Option("mock"),
    ssh_user: str = typer.Option(""),
    ssh_host: str = typer.Option(""),
    ssh_port: int = typer.Option(22),
    ssh_key: str | None = typer.Option(None),
    sse_url: str = typer.Option(""),
    sse_auth_token_env: str | None = typer.Option(None),
) -> None:
    """Print the settings.json content that ``install`` would write."""
    if transport == "stdio-local":
        cfg = TransportConfig(transport="stdio-local", adapter_mode=adapter_mode)
    elif transport == "stdio-ssh":
        cfg = TransportConfig(
            transport="stdio-ssh",
            ssh_user=ssh_user, ssh_host=ssh_host, ssh_port=ssh_port, ssh_key=ssh_key,
        )
    elif transport == "sse-http":
        cfg = TransportConfig(
            transport="sse-http", sse_url=sse_url, sse_auth_token_env=sse_auth_token_env,
        )
    else:
        typer.echo(f"Unknown transport: {transport}", err=True)
        raise typer.Exit(code=2)
    typer.echo(json.dumps(cfg.to_settings(), indent=2))


# --- uninstall -------------------------------------------------------------


@app.command()
def uninstall(
    client: str = typer.Option("claude_code"),
    project_root: str | None = typer.Option(None),
) -> None:
    """Remove the bundled skill files (settings.json is preserved)."""
    root = Path(project_root) if project_root else Path.cwd()
    try:
        prov = get_provisioner(client)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2) from None
    result = prov.uninstall(root)
    typer.echo(f"Uninstalled {result.client} from {result.skills_dir}")
    for note in result.notes:
        typer.echo(f"  {note}")


# --- connect-test ----------------------------------------------------------


@app.command("connect-test")
def connect_test(
    transport: str = typer.Argument(..., help="stdio-local | stdio-ssh | sse-http"),
    server_command: str = typer.Option("python", help="(stdio-local) command to test"),
    ssh_user: str = typer.Option(""),
    ssh_host: str = typer.Option(""),
    ssh_port: int = typer.Option(22),
    ssh_key: str | None = typer.Option(None),
    server: str = typer.Option("python -m quad.mcp.server", help="(stdio-ssh) remote command"),
    sse_url: str = typer.Option("", help="(sse-http) URL"),
    auth_token: str | None = typer.Option(None, help="(sse-http) bearer token"),
) -> None:
    """Verify a transport works without writing any files. Exits non-zero on failure."""
    kwargs: dict[str, Any] = {}
    if transport == "stdio-local":
        kwargs = {"command": server_command}
    elif transport == "stdio-ssh":
        if not ssh_host or not ssh_user:
            typer.echo("stdio-ssh requires --ssh-user and --ssh-host", err=True)
            raise typer.Exit(code=2)
        kwargs = {
            "ssh_user": ssh_user,
            "ssh_host": ssh_host,
            "ssh_port": ssh_port,
            "ssh_key": ssh_key,
            "server_command": server,
        }
    elif transport == "sse-http":
        # Trap the "silently tested a blank URL" pitfall from escalation #63.
        # An agent that runs `--sse-url "$FOO" --auth-token "$BAR"` where
        # either shell var was never exported (common when .env is empty and
        # the token actually lives in Windows User env / settings.json's
        # ${env:...} expansion) ends up probing "" and getting a
        # false-negative failure. Reject blank / whitespace-only inputs
        # up front with an actionable message.
        if not sse_url or not sse_url.strip():
            typer.echo(
                "sse-http: --sse-url is empty. This usually means the shell "
                "variable you passed (e.g. \"$QUAD_MCP_URL\") is not set. "
                "Read the URL from .claude/settings.json (mcpServers.quad.url) "
                "and pass it as a literal, or export the variable first.",
                err=True,
            )
            raise typer.Exit(code=2)
        if auth_token is not None and not auth_token.strip():
            typer.echo(
                "sse-http: --auth-token is empty. The bearer token likely "
                "lives in a User-level env var referenced by "
                ".claude/settings.json as ${env:QUAD_MCP_TOKEN} (install.ps1 "
                "does NOT write it into .env). Start a fresh shell so the "
                "User env var is in scope, or pass the token literally.",
                err=True,
            )
            raise typer.Exit(code=2)
        kwargs = {"url": sse_url, "auth_token": auth_token}
    else:
        typer.echo(f"Unknown transport: {transport}", err=True)
        raise typer.Exit(code=2)

    result = probe(transport, **kwargs)  # type: ignore[arg-type]
    typer.echo(result.render())
    if not result.ok:
        raise typer.Exit(code=1)


# --- detect (local hardware probe) ----------------------------------------


@app.command()
def detect(
    platform: str | None = typer.Option(None, help="windows|linux|android|macos (auto-detected if omitted)"),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of markdown"),
    no_enrich: bool = typer.Option(False, "--no-enrich", help="Skip ui/tips fields"),
    no_sdk_probe: bool = typer.Option(False, "--no-sdk-probe", help="Skip qnn-platform-validator call"),
    local_only: bool = typer.Option(
        False, "--local-only",
        help="Use only the client-side static probe; do not query the server.",
    ),
) -> None:
    """Detect hardware. Prefers the server's authoritative (registry-enriched)
    hardware_detect; falls back to a local static probe when the server is
    unreachable (or with --local-only). The result's ``discovery_source`` field
    records which path answered."""
    from .local import detect_hardware, detect_hardware_server_first

    if local_only:
        profile = detect_hardware(
            platform=platform, enrich=not no_enrich, sdk_probe=not no_sdk_probe
        )
    else:
        profile = detect_hardware_server_first(
            platform=platform, enrich=not no_enrich, sdk_probe=not no_sdk_probe
        )
    if json_out:
        typer.echo(json.dumps(profile, indent=2, default=str))
    elif "ui" in profile:
        typer.echo(profile["ui"])
        if profile.get("tips"):
            typer.echo("")
            for tip in profile["tips"]:
                typer.echo(f"- {tip}")
    else:
        typer.echo(json.dumps(profile, indent=2, default=str))


# --- profile-device (client-agent: server plans, we execute locally) ------


@app.command("profile-device")
def profile_device(
    model: str = typer.Option("", "--model", help="Local model path (.bin/.dlc/.onnx) on THIS machine. For --convert, the local source file to upload."),
    model_from_server: str = typer.Option("", "--model-from-server", help="Download the model from the server first: paste the download_url from a prior convert_model result."),
    sha256: str | None = typer.Option(None, "--sha256", help="Expected sha256 for --model-from-server (integrity check)."),
    convert: bool = typer.Option(False, "--convert", help="Convert/quantize on the server first, then profile the produced artifact."),
    source_format: str = typer.Option("onnx", "--source-format", help="(--convert) onnx | pytorch | tensorflow | tflite"),
    target_sdk: str = typer.Option("qnn", "--target-sdk", help="(--convert) qnn | snpe | nwaios | executorch"),
    quantization: str = typer.Option("fp32", "--quantization", help="(--convert) fp32 | int8 | int4"),
    model_source_json: str | None = typer.Option(None, "--model-source-json", help="(--convert) explicit model_source dict as JSON (huggingface/github/url/server_path)."),
    model_id: str | None = typer.Option(None, "--model-id", help="(--convert) AI Hub Models catalog id."),
    keep: bool = typer.Option(False, "--keep", help="Keep the fetched/converted artifact instead of deleting it after profiling."),
    transport: str = typer.Option("ssh", "--transport", help="ssh | adb"),
    host: str = typer.Option("", "--host", help="(ssh) board IP/hostname"),
    user: str = typer.Option("root", "--user", help="(ssh) login user"),
    port: int = typer.Option(22, "--port", help="(ssh) port"),
    key: str | None = typer.Option(None, "--key", help="(ssh) private key path"),
    serial: str = typer.Option("", "--serial", help="(adb) device serial (blank = default device)"),
    runtime: str = typer.Option("auto", "--runtime", help="cpu | gpu | npu | auto"),
    duration_s: int = typer.Option(10, "--duration", help="profiling window (seconds)"),
    url: str | None = typer.Option(None, "--url", help="MCP server URL (else QUAD_MCP_URL / settings.json)"),
    token: str | None = typer.Option(None, "--token", help="MCP bearer token (else env / settings.json)"),
    json_out: bool = typer.Option(False, "--json", help="Emit the full report JSON instead of markdown."),
) -> None:
    """Profile a local board using a (possibly remote/cloud) MCP server.

    The server can't reach a board on your bench, so it hands us a plan; we run
    it locally over SSH/ADB and send the raw outputs back for the server to turn
    into a comprehensive report.

    The model reaches the board one of three ways (pick exactly one):

    \b
      --model <path>              a file already on THIS machine.
      --model-from-server <url>   download a server artifact first (paste the
                                  download_url from a prior convert_model result).
      --convert                   convert/quantize on the server, download the
                                  produced .bin/.dlc, then profile it — the full
                                  convert -> download -> profile-on-my-board chain.

    --model-from-server and --convert need a hosted (sse-http) server URL.
    """
    import asyncio
    import tempfile

    from .client import create_client
    from .local import device_agent

    # ── Exactly one model source ────────────────────────────────────────────
    sources = [bool(model and not convert), bool(model_from_server), bool(convert)]
    if sum(sources) != 1:
        typer.echo(
            "[FAIL] provide exactly one model source: --model <local>, "
            "--model-from-server <url>, or --convert (with --model/--model-source-json/--model-id).",
            err=True,
        )
        raise typer.Exit(code=2)

    if convert and not (model or model_source_json or model_id):
        typer.echo("[FAIL] --convert needs an input: --model <local file>, --model-source-json, or --model-id.", err=True)
        raise typer.Exit(code=2)

    # ── Transport target ─────────────────────────────────────────────────────
    if transport == "ssh":
        if not host:
            typer.echo("[FAIL] ssh transport requires --host", err=True)
            raise typer.Exit(code=2)
        target = _ssh_target(host, user, port, key)
    elif transport == "adb":
        from .local.board.adb import ADBTarget

        target = ADBTarget(serial=serial)
    else:
        typer.echo(f"[FAIL] unknown transport {transport!r} (ssh | adb)", err=True)
        raise typer.Exit(code=2)

    # Local source can be validated up front.
    if model and not convert and not Path(model).is_file():
        typer.echo(f"[FAIL] model not found on this machine: {model}", err=True)
        raise typer.Exit(code=2)

    tmp_dir = Path(tempfile.mkdtemp(prefix="quad_profile_"))
    notes: list[str] = []

    async def _run() -> dict[str, Any]:
        async with create_client(url=url, token=token) as client:
            # ── Resolve the model to a local path. ───────────────────────────
            if model and not convert:
                model_path = Path(model)
            elif model_from_server:
                model_path = await client.download_artifact(
                    model_from_server, tmp_dir, expected_sha256=sha256
                )
                notes.append(f"downloaded from server -> {model_path.name}")
            else:  # --convert
                conv_args: dict[str, Any] = {
                    "source_format": source_format,
                    "target_sdk": target_sdk,
                    "quantization": quantization,
                    "auto_download": True,
                    "download_dir": str(tmp_dir),
                }
                if model:
                    conv_args["upload"] = model  # upload the local source
                if model_source_json:
                    conv_args["model_source"] = json.loads(model_source_json)
                if model_id:
                    conv_args["model_id"] = model_id
                res = await client.convert_model(**conv_args)
                local = res.get("local_path")
                if not local:
                    warns = "; ".join(res.get("warnings", [])) or "no download_url on the convert result"
                    return {"error": f"convert produced no local artifact to profile ({warns})",
                            "decisions": res.get("decisions", [])}
                model_path = Path(local)
                notes.append(f"converted ({target_sdk}/{quantization}) -> {model_path.name}")
                for d in res.get("decisions", []):
                    notes.append(f"decision: {d.get('choice', '')}")

            if not model_path.is_file():
                return {"error": f"resolved model not found locally: {model_path}"}

            # 1. Ask the server for a plan (no device touched server-side).
            plan = await client.call_tool_dict("profile_device_plan", {
                "model_name": model_path.name,
                "runtime": runtime,
                "duration_s": duration_s,
            })
            # 2. Execute the plan locally against the board.
            execd = device_agent.execute_plan(
                plan, model_path=model_path, transport=transport, target=target
            )
            if execd.get("error"):
                return {"error": execd["error"], "log": execd.get("log", [])}
            # 3. Send raw outputs back; the server builds the report.
            report = await client.call_tool_dict("profile_device_report", {
                "plan": plan,
                "step_outputs": execd["step_outputs"],
                "device_info": execd["device_info"],
                "address": host or serial or "(device)",
                "transport": transport,
                "model_size_mb": round(model_path.stat().st_size / (1024 * 1024), 3),
            })
            return report

    try:
        report = asyncio.run(_run())
    except Exception as e:  # noqa: BLE001 — surface connection/tool errors cleanly
        typer.echo(f"[FAIL] {e}", err=True)
        raise typer.Exit(code=1) from e
    finally:
        if not keep:
            import shutil

            shutil.rmtree(tmp_dir, ignore_errors=True)

    if report.get("error"):
        typer.echo(f"[FAIL] {report['error']}", err=True)
        raise typer.Exit(code=1)
    for n in notes:
        typer.echo(f"[i] {n}")
    if json_out:
        typer.echo(json.dumps(report, indent=2, default=str))
    else:
        typer.echo(report.get("report_md") or json.dumps(report, indent=2, default=str))


# --- doctor (local diagnostic suite) --------------------------------------


@app.command()
def doctor(
    real_mode: bool = typer.Option(False, "--real-mode", help="Escalate SDK warnings to failures."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of markdown."),
) -> None:
    """Run the local diagnostic suite. Local-only checks; for AIMET/AI Hub Models/QHAS use the MCP doctor."""
    from .local import has_failures, run_doctor
    from .local.render import format_doctor

    results = run_doctor(real_mode=real_mode)
    if json_out:
        typer.echo(json.dumps(results, indent=2, default=str))
    else:
        typer.echo(format_doctor(results))
    if real_mode and has_failures(results):
        raise typer.Exit(code=1)


# --- unoq (UNO Q / QCS2210 board ops) -------------------------------------


unoq = typer.Typer(help="UNO Q / QCS2210 board operations (SSH-driven, local-only).")
app.add_typer(unoq, name="unoq")


def _ssh_target(
    host: str,
    user: str,
    port: int,
    key: str | None,
) -> Any:
    """Build an SSHTarget from CLI flags (lazy import to avoid hardware imports for unrelated commands)."""
    from .local.board.ssh import SSHTarget
    return SSHTarget(
        host=host,
        user=user,
        port=port,
        key=Path(key).expanduser() if key else None,
    )


def _emit(result: Any, json_out: bool) -> None:
    if json_out:
        from dataclasses import asdict
        typer.echo(json.dumps(asdict(result), indent=2, default=str))
    else:
        glyph = "[OK]" if result.ok else "[FAIL]"
        typer.echo(f"{glyph} {result.op} -- {result.summary} ({result.elapsed_ms:.0f} ms)")
        for label, detail in result.details.items():
            if isinstance(detail, dict):
                stdout = detail.get("stdout", "")
                if stdout:
                    typer.echo(f"\n--- {label} ---")
                    typer.echo(stdout[:2000])
            elif isinstance(detail, str) and detail:
                typer.echo(f"\n--- {label} ---")
                typer.echo(detail[:2000])
    if not result.ok:
        raise typer.Exit(code=1)


@unoq.command()
def status(
    host: str = typer.Argument(..., help="Board IP/hostname"),
    user: str = typer.Option("root"),
    port: int = typer.Option(22),
    key: str | None = typer.Option(None, help="SSH private key path"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Health, connectivity, and resource snapshot."""
    from .local.board import commands as ops
    _emit(ops.status(_ssh_target(host, user, port, key)), json_out)


@unoq.command()
def configure(
    host: str = typer.Argument(...),
    user: str = typer.Option("root"),
    workspace: str = typer.Option("/data/local/tmp/quad/"),
    board: str = typer.Option("arduino-unoq", help="Board profile: arduino-unoq | iq9075"),
    port: int = typer.Option(22, help="SSH port"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Emit a quad.toml [target.*] stanza for board configuration."""
    from .local.board import commands as ops
    result = ops.configure_template(
        host=host, user=user, workspace=workspace, board=board, port=port
    )
    if json_out:
        from dataclasses import asdict
        typer.echo(json.dumps(asdict(result), indent=2, default=str))
    else:
        typer.echo(result.details["toml"])


@unoq.command()
def deploy(
    host: str = typer.Argument(...),
    app_path: Path = typer.Option(..., "--app", help="Local app binary/script"),
    model: Path = typer.Option(..., "--model", help="Local model file (.dlc/.bin)"),
    user: str = typer.Option("root"),
    port: int = typer.Option(22),
    key: str | None = typer.Option(None),
    workspace: str = typer.Option("/data/local/tmp/quad/"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Push app + model to the board and verify the artifacts landed."""
    from .local.board import commands as ops
    _emit(
        ops.deploy(_ssh_target(host, user, port, key), app_path=app_path, model_path=model, workspace=workspace),
        json_out,
    )


@unoq.command()
def firmware(
    host: str = typer.Argument(...),
    user: str = typer.Option("root"),
    port: int = typer.Option(22),
    key: str | None = typer.Option(None),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Read-only firmware/BSP info (build version, kernel, DSP skel, SNPE libs)."""
    from .local.board import commands as ops
    _emit(ops.firmware_info(_ssh_target(host, user, port, key)), json_out)


@unoq.command()
def logs(
    host: str = typer.Argument(...),
    user: str = typer.Option("root"),
    port: int = typer.Option(22),
    key: str | None = typer.Option(None),
    since_minutes: int = typer.Option(60, "--since", help="journalctl --since N minutes"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Pull recent kernel, journal, SNPE, and DSP-trace logs."""
    from .local.board import commands as ops
    _emit(ops.logs(_ssh_target(host, user, port, key), since_minutes=since_minutes), json_out)


@unoq.command()
def debug(
    host: str = typer.Argument(...),
    user: str = typer.Option("root"),
    port: int = typer.Option(22),
    key: str | None = typer.Option(None),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Diagnostic checklist (DSP state, SNPE version, kernel errors, recent crashes)."""
    from .local.board import commands as ops
    _emit(ops.debug(_ssh_target(host, user, port, key)), json_out)


@unoq.command()
def perf(
    host: str = typer.Argument(...),
    model: str = typer.Option(..., "--model", help="Path to .dlc on the device"),
    duration_s: int = typer.Option(30, "--duration"),
    perf_profile: str = typer.Option("burst", "--profile"),
    user: str = typer.Option("root"),
    port: int = typer.Option(22),
    key: str | None = typer.Option(None),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Run snpe-net-run with --debug and return the latency lines."""
    from .local.board import commands as ops
    _emit(
        ops.perf(_ssh_target(host, user, port, key), model_path=model, duration_s=duration_s, perf_profile=perf_profile),
        json_out,
    )


@unoq.command()
def stability(
    host: str = typer.Argument(...),
    model: str = typer.Option(..., "--model"),
    duration_s: int = typer.Option(3600, "--duration"),
    user: str = typer.Option("root"),
    port: int = typer.Option(22),
    key: str | None = typer.Option(None),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Kick off a soak test in the background. Returns the remote PID."""
    from .local.board import commands as ops
    _emit(
        ops.stability_kickoff(_ssh_target(host, user, port, key), model_path=model, duration_s=duration_s),
        json_out,
    )


@unoq.command()
def power(
    host: str = typer.Argument(...),
    user: str = typer.Option("root"),
    port: int = typer.Option(22),
    key: str | None = typer.Option(None),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Sample INA / cpufreq / GPU clock / thermal sensors."""
    from .local.board import commands as ops
    _emit(ops.power(_ssh_target(host, user, port, key)), json_out)


@unoq.command(name="app")
def app_cmd(
    host: str = typer.Argument(...),
    name: str = typer.Argument(..., help="App name registered as quad-inference@<name>"),
    action: str = typer.Option("status", "--action", help="start|stop|restart|status"),
    user: str = typer.Option("root"),
    port: int = typer.Option(22),
    key: str | None = typer.Option(None),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Manage a deployed app via systemctl quad-inference@<name>."""
    from .local.board import commands as ops
    _emit(ops.app_lifecycle(_ssh_target(host, user, port, key), action=action, app_name=name), json_out)


@unoq.command()
def ota(
    host: str = typer.Argument(...),
    archive: Path = typer.Option(..., "--archive", help="Local .tar.gz to push and extract"),
    user: str = typer.Option("root"),
    port: int = typer.Option(22),
    key: str | None = typer.Option(None),
    workspace: str = typer.Option("/data/local/tmp/quad/"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Push an update archive and extract under the workspace."""
    from .local.board import commands as ops
    _emit(ops.ota(_ssh_target(host, user, port, key), archive=archive, workspace=workspace), json_out)


@unoq.command()
def test(
    host: str = typer.Argument(...),
    user: str = typer.Option("root"),
    port: int = typer.Option(22),
    key: str | None = typer.Option(None),
    workspace: str = typer.Option("/data/local/tmp/quad/"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Invoke the on-device run_tests.sh suite and stream its stdout back."""
    from .local.board import commands as ops
    _emit(ops.run_test_suite(_ssh_target(host, user, port, key), workspace=workspace), json_out)


def cli() -> None:
    """Entry point for the ``quad-client`` script."""
    # On Windows the default console code page is cp1252, which can't encode
    # the ✓/✗/→ glyphs the probe renderer emits. Reconfigure to UTF-8 with
    # 'replace' so we degrade to '?' on legacy terminals instead of crashing
    # the whole command after the probe has already succeeded.
    import contextlib
    import sys
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, OSError):
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    app()


if __name__ == "__main__":
    cli()
