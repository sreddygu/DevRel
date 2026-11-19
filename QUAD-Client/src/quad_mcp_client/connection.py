"""MCP server connection probing — verify reachability before provisioning.

The client install needs to confirm that the MCP server it's about to
configure Claude Code to invoke is actually reachable. Three transports
are supported:

1. **stdio-local**  — the server runs on the same machine; Claude Code
                       spawns it as a child process. Probe = launch the
                       command and verify it starts cleanly.

2. **stdio-ssh**    — the server runs on a remote machine; Claude Code
                       proxies through SSH (``ssh user@host python -m quad.mcp.server``).
                       Probe = SSH to the host and run the same command,
                       verify ``python -c "import quad.mcp.server"`` succeeds.

3. **sse-http**     — the server runs as a remote HTTP service speaking
                       MCP over Server-Sent Events. Probe = HTTP GET on
                       the URL, verify a 200 / 405 / 404 (any 4xx that
                       isn't 401/403 means the URL is reachable; auth
                       failure is also ``reachable``).

Every probe returns a :class:`ConnectionProbeResult` with:
  * ``ok`` — boolean
  * ``transport`` — which transport was tested
  * ``latency_ms`` — measured handshake time
  * ``error`` — exception message on failure
  * ``hint`` — human-readable next-step suggestion when ok is False
  * ``details`` — extra data (server version, tool count, etc.) when known

The probe is best-effort — it never raises. Failures should be reported
to the user with the hint, but shouldn't block them from completing the
install (the user may be intentionally provisioning before the server is
running).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)


Transport = Literal["stdio-local", "stdio-ssh", "sse-http"]


def _resolve_command(command: str) -> str | None:
    """Resolve a command to an executable path, with Windows-friendly fallbacks.

    ``shutil.which`` is the right answer for bare names ("python") and for
    absolute paths whose on-disk filename matches verbatim. It falls down
    in two real-world cases:

    1. Absolute paths handed in without a Windows extension (e.g. an MSYS
       `.../Scripts/python` produced by Git Bash, where the actual file
       is `python.exe`). ``shutil.which`` does not auto-append PATHEXT
       extensions for absolute paths.

    2. Paths containing ``..`` segments — fine for the OS, but easy to
       mismatch against PATH lookups.

    For any input that looks like a path (contains a separator), we also
    try ``os.path.exists`` directly and re-try with each PATHEXT
    extension before giving up.
    """
    hit = shutil.which(command)
    if hit is not None:
        return hit

    looks_like_path = (os.sep in command) or ("/" in command)
    if not looks_like_path:
        return None

    if os.path.isfile(command):
        return command

    if os.name == "nt":
        for ext in os.environ.get("PATHEXT", ".EXE;.CMD;.BAT").split(os.pathsep):
            candidate = command + ext.lower()
            if os.path.isfile(candidate):
                return candidate
            candidate = command + ext
            if os.path.isfile(candidate):
                return candidate

    return None


@dataclass
class ConnectionProbeResult:
    """Outcome of a connection probe."""

    ok: bool
    transport: Transport
    latency_ms: float = 0.0
    error: str = ""
    hint: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def render(self) -> str:
        """Human-readable single-string summary."""
        if self.ok:
            # A verified MCP initialize handshake is the strongest signal —
            # surface the server name/version instead of the raw details dict.
            if self.details.get("handshake") == "initialize":
                name = self.details.get("server_name") or "MCP server"
                ver = self.details.get("server_version")
                who = f"{name} {ver}".strip()
                return (
                    f"✓ {self.transport} connected in {self.latency_ms:.0f} ms "
                    f"— MCP handshake OK ({who})"
                )
            return (
                f"✓ {self.transport} reachable in {self.latency_ms:.0f} ms"
                + (f" — {self.details}" if self.details else "")
            )
        msg = f"✗ {self.transport} probe failed: {self.error}"
        if self.hint:
            msg += f"\n  → {self.hint}"
        return msg


# --- Probe: stdio-local ----------------------------------------------------


def probe_stdio_local(
    command: str = "python",
    args: list[str] | None = None,
    *,
    timeout_s: float = 8.0,
    env: dict[str, str] | None = None,
) -> ConnectionProbeResult:
    """Verify the local MCP server can start.

    Launches ``command args`` as a subprocess. Doesn't actually speak
    MCP — just verifies the process starts, stays running for ~1 second,
    and exits cleanly when terminated. This catches the common failures:
    Python missing, package not importable, syntax errors at import time.
    """
    if args is None:
        # ``-u`` forces unbuffered stdout: required on Windows, where
        # Python's block-buffered pipe holds JSON-RPC responses until
        # the buffer fills. Harmless on Unix.
        args = ["-u", "-m", "quad.mcp.server"]

    cmd_path = _resolve_command(command)
    if cmd_path is None:
        return ConnectionProbeResult(
            ok=False,
            transport="stdio-local",
            error=f"Command not found on PATH: {command!r}",
            hint=(
                f"Install Python 3.10+ and ensure 'python' (or {command!r}) is on PATH. "
                "Run: where python (Windows) or which python (POSIX)."
            ),
        )

    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    # Pre-flight: verify the chosen Python is >= 3.10 AND has quad-agent
    # installed. Uses find_spec rather than `import quad.mcp.server` —
    # importing the server pulls in jinja2 + codegen + sdk_manager
    # (~13s cold start), which blew the old 10s budget. Syntax errors
    # inside server.py surface from the real subprocess launch below.
    try:
        preflight = subprocess.run(
            [
                cmd_path,
                "-c",
                (
                    "import sys; "
                    "ver = sys.version_info[:2]; "
                    "assert ver >= (3, 10), f'python {ver} too old (need >=3.10)'; "
                    "import importlib.util; "
                    "assert importlib.util.find_spec('quad') is not None, "
                    "'quad-agent not installed'"
                ),
            ],
            capture_output=True,
            text=True,
            timeout=30.0,
            env=full_env,
        )
    except FileNotFoundError as e:
        return ConnectionProbeResult(
            ok=False,
            transport="stdio-local",
            error=str(e),
            hint=(
                f"Could not exec {cmd_path!r}. Check that the interpreter exists "
                "and is on PATH (Windows may need the .exe suffix)."
            ),
        )
    if preflight.returncode != 0:
        stderr = preflight.stderr.strip()
        if "AssertionError" in stderr and "too old" in stderr:
            hint = (
                f"{command!r} is a Python older than 3.10. Install Python 3.10+ and "
                "either put it first on PATH or pass --command <path-to-newer-python>."
            )
        elif (
            "AssertionError" in stderr and "not installed" in stderr
        ) or "ModuleNotFoundError" in stderr or "No module named" in stderr:
            hint = (
                f"quad-agent is not importable by {command!r}. Activate the venv "
                "where you installed quad-agent, or run: "
                f"{command} -m pip install quad-agent."
            )
        else:
            hint = (
                f"{command!r} preflight failed. Check the install. "
                f"stderr:\n  {stderr[:500]}"
            )
        return ConnectionProbeResult(
            ok=False,
            transport="stdio-local",
            error=f"preflight failed: {stderr.splitlines()[-1] if stderr else 'unknown'}",
            hint=hint,
            details={"returncode": preflight.returncode, "stderr_excerpt": stderr[:500]},
        )

    start = time.perf_counter()
    try:
        proc = subprocess.Popen(
            [cmd_path, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=full_env,
        )
    except FileNotFoundError as e:
        return ConnectionProbeResult(
            ok=False,
            transport="stdio-local",
            error=str(e),
            hint=f"Could not exec {command!r}. Check PATH and permissions.",
        )

    # Give it up to ~1 second to confirm it didn't crash on startup
    try:
        # If it exits within 1s, that's a startup error
        rc = proc.wait(timeout=1.0)
        elapsed = (time.perf_counter() - start) * 1000.0
        stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
        return ConnectionProbeResult(
            ok=False,
            transport="stdio-local",
            latency_ms=elapsed,
            error=f"server exited immediately with code {rc}",
            hint=(
                "MCP server crashed during startup. Check that the package is "
                f"importable: python -c 'import quad.mcp.server'. stderr:\n  {stderr.strip()[:500]}"
            ),
            details={"returncode": rc, "stderr_excerpt": stderr.strip()[:500]},
        )
    except subprocess.TimeoutExpired:
        # Good — it didn't crash. Now terminate cleanly.
        elapsed = (time.perf_counter() - start) * 1000.0
        proc.terminate()
        try:
            proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            proc.kill()
        return ConnectionProbeResult(
            ok=True,
            transport="stdio-local",
            latency_ms=elapsed,
            details={"command": command, "args": args},
        )


# --- Probe: stdio-ssh ------------------------------------------------------


def probe_stdio_ssh(
    ssh_user: str,
    ssh_host: str,
    *,
    ssh_port: int = 22,
    ssh_key: str | None = None,
    server_command: str = "python -m quad.mcp.server",
    timeout_s: float = 12.0,
) -> ConnectionProbeResult:
    """Verify a remote MCP server is reachable + the package is importable there.

    Runs ``ssh user@host python -c 'import quad.mcp.server'`` and checks
    the exit code. Doesn't actually speak MCP — just confirms the
    plumbing works.
    """
    if not shutil.which("ssh"):
        return ConnectionProbeResult(
            ok=False,
            transport="stdio-ssh",
            error="ssh command not found on PATH",
            hint=(
                "Install OpenSSH client. On Windows: winget install Microsoft.OpenSSH.Client. "
                "On macOS/Linux: usually preinstalled."
            ),
        )

    # We can probe with: ssh -o BatchMode=yes -o ConnectTimeout=N user@host
    #     python -c "import quad.mcp.server"
    ssh_cmd = ["ssh", "-p", str(ssh_port)]
    if ssh_key:
        ssh_cmd += ["-i", ssh_key]
    # BatchMode prevents prompting for password — fail fast if key auth doesn't work
    ssh_cmd += [
        "-o", "BatchMode=yes",
        "-o", f"ConnectTimeout={int(timeout_s)}",
        "-o", "StrictHostKeyChecking=accept-new",
        f"{ssh_user}@{ssh_host}",
    ]
    # Build the remote probe — import the server module using the SAME
    # interpreter the caller will actually launch over stdio-ssh. Deriving
    # it from server_command avoids a false PASS/FAIL when the caller uses a
    # venv-scoped or absolute-path Python (bare `python` may be absent or a
    # different interpreter on the remote host).
    import shlex as _shlex

    try:
        _server_tokens = _shlex.split(server_command)
    except ValueError:
        _server_tokens = server_command.split()
    remote_python = _server_tokens[0] if _server_tokens else "python3"
    probe = f"{_shlex.quote(remote_python)} -c 'import quad.mcp.server; print(\"OK\")'"
    ssh_cmd.append(probe)

    start = time.perf_counter()
    try:
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return ConnectionProbeResult(
            ok=False,
            transport="stdio-ssh",
            latency_ms=timeout_s * 1000.0,
            error=f"SSH connection timed out after {timeout_s}s",
            hint=(
                f"Could not reach {ssh_host}:{ssh_port}. Check the host is up, "
                "the port is open, and your SSH key is configured. "
                f"Test manually: ssh -p {ssh_port} {ssh_user}@{ssh_host}"
            ),
        )

    elapsed = (time.perf_counter() - start) * 1000.0
    if result.returncode == 0 and "OK" in result.stdout:
        return ConnectionProbeResult(
            ok=True,
            transport="stdio-ssh",
            latency_ms=elapsed,
            details={
                "host": ssh_host,
                "user": ssh_user,
                "port": ssh_port,
            },
        )

    # Diagnose common failures
    stderr = result.stderr.strip()
    if "Permission denied" in stderr or "publickey" in stderr.lower():
        hint = (
            f"SSH key auth to {ssh_user}@{ssh_host} failed. Add your public key "
            "to the server's ~/.ssh/authorized_keys, or specify a key with --ssh-key."
        )
    elif "Could not resolve hostname" in stderr or "Name or service not known" in stderr:
        hint = f"Hostname {ssh_host!r} did not resolve. Check spelling and DNS."
    elif "ModuleNotFoundError" in result.stderr or "ImportError" in result.stderr:
        hint = (
            f"SSH worked but quad.mcp.server isn't importable on {ssh_host}. "
            "Install the QUAD server package on the remote machine: "
            "https://github.qualcomm.com/pavanr/QUAD"
        )
    else:
        hint = "Check stderr above + run the ssh command manually to debug."

    return ConnectionProbeResult(
        ok=False,
        transport="stdio-ssh",
        latency_ms=elapsed,
        error=f"ssh exit {result.returncode}: {stderr[:300]}",
        hint=hint,
        details={
            "returncode": result.returncode,
            "stderr_excerpt": stderr[:500],
        },
    )


# --- Probe: sse-http -------------------------------------------------------


# Map a handful of common invisible characters to readable names so the hint
# can tell the user *what* is wrong, not just "char at position N".
_CTRL_CHAR_NAMES = {
    "\x00": "NUL",
    "\t": "TAB",
    "\n": "newline (LF)",
    "\r": "carriage return (CR)",
    "\x16": "SYN (Ctrl-V paste artifact)",
    "\x1b": "ESC",
    "﻿": "BOM (zero-width no-break space)",
    "​": "zero-width space",
    "\xa0": "non-breaking space",
}


def _check_url_printable(url: str) -> ConnectionProbeResult | None:
    """Reject a URL containing control / non-printable characters early.

    A control char in the URL (most often ``\\x16`` SYN from a Ctrl-V terminal
    paste, or a BOM / zero-width space copied from a web page or chat) makes
    ``httpx`` raise ``InvalidURL`` deep in the request, surfacing a cryptic
    "Invalid non-printable ASCII character" with a useless "debug with curl"
    hint — curl can't help because the *string itself* is corrupt before any
    request is made. Catch it here with a precise, actionable message instead.

    Returns a failing :class:`ConnectionProbeResult` when a bad character is
    found, else ``None`` (URL is clean).
    """
    for idx, ch in enumerate(url):
        # Printable ASCII (0x20–0x7e) and ordinary higher Unicode are fine; flag
        # C0/C1 control chars and the invisible-whitespace lookalikes above.
        is_control = ch < " " or ch == "\x7f" or ("\x80" <= ch <= "\x9f")
        if is_control or ch in _CTRL_CHAR_NAMES:
            name = _CTRL_CHAR_NAMES.get(ch, f"U+{ord(ch):04X}")
            return ConnectionProbeResult(
                ok=False,
                transport="sse-http",
                error=(
                    f"URL contains a non-printable character ({name}, "
                    f"\\x{ord(ch):02x}) at position {idx}"
                ),
                hint=(
                    "The URL has a hidden control character — almost always a "
                    "copy-paste artifact (Ctrl-V in the terminal, or an invisible "
                    "space / BOM copied from a web page or chat). It is NOT a "
                    "server problem, so curl won't help. Retype the URL by hand "
                    "(don't paste), or strip control chars first, e.g.:\n"
                    "    URL=$(printf %s \"$URL\" | tr -d '[:cntrl:]')\n"
                    "  Then re-run with --sse-url \"$URL\"."
                ),
            )
    return None


# A minimal, spec-valid MCP `initialize` request. Posting this is the only way
# to *prove* the endpoint speaks MCP and accepts the supplied token — a bare GET
# only tells us something is listening. Streamable-HTTP servers answer with a
# single JSON object or an `event: message\ndata: {…}` SSE frame; we handle both.
_MCP_INITIALIZE_BODY = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "quad-mcp-client.connect-test", "version": "1"},
    },
}


def _server_info_from_initialize(text: str) -> dict[str, Any] | None:
    """Extract ``result.serverInfo`` from an MCP ``initialize`` response body.

    Accepts either a plain JSON-RPC object or a Server-Sent-Events frame
    (``event: message`` / ``data: {…}``) — Streamable-HTTP servers may use
    either. Returns the ``serverInfo`` dict on a successful handshake, else
    ``None`` (malformed, an error response, or not an initialize result).
    """
    if not text:
        return None
    candidates: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            candidates.append(line[len("data:"):].strip())
    candidates.append(text.strip())  # also try the body verbatim (plain JSON)
    for raw in candidates:
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict):
            result = obj.get("result")
            if isinstance(result, dict) and isinstance(result.get("serverInfo"), dict):
                return result["serverInfo"]
    return None


def _try_mcp_initialize(
    url: str,
    *,
    auth_token: str | None,
    timeout_s: float,
) -> ConnectionProbeResult | None:
    """Attempt a real MCP ``initialize`` POST handshake.

    Returns a *decisive* :class:`ConnectionProbeResult` when the outcome is
    unambiguous:
      * a verified ``serverInfo`` response  -> hard pass (handshake="initialize")
      * 401/403                              -> auth failure (the token is wrong)
    Returns ``None`` when the POST is inconclusive (wrong method/path, server
    only does SSE-GET, network hiccup, etc.) so the caller falls back to the
    lenient GET reachability probe rather than failing a usable server.
    """
    try:
        import httpx
    except ImportError:
        return None

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    start = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout_s, follow_redirects=False) as client:
            response = client.post(url, headers=headers, json=_MCP_INITIALIZE_BODY)
        elapsed = (time.perf_counter() - start) * 1000.0
    except Exception:
        # Network-level failure on the POST is inconclusive here; the GET probe
        # that follows will classify connection-refused / timeout properly.
        return None

    code = response.status_code
    server_header = response.headers.get("server", "")

    if code in (401, 403):
        return ConnectionProbeResult(
            ok=False,
            transport="sse-http",
            latency_ms=elapsed,
            error=f"auth failed: HTTP {code}",
            hint=(
                "Server is reachable and speaks MCP, but the bearer token was "
                "rejected. Set the correct token (e.g. export QUAD_MCP_TOKEN=…) "
                "and retry."
            ),
            details={"status_code": code, "server": server_header},
        )

    if 200 <= code < 300:
        info = _server_info_from_initialize(response.text or "")
        if info is not None:
            return ConnectionProbeResult(
                ok=True,
                transport="sse-http",
                latency_ms=elapsed,
                details={
                    "status_code": code,
                    "server": server_header,
                    "handshake": "initialize",
                    "server_name": info.get("name", ""),
                    "server_version": info.get("version", ""),
                },
            )

    # Anything else (405 method-not-allowed on an SSE-only route, a non-MCP
    # 2xx, a 400 without a verified result) is inconclusive -> fall back.
    return None


def probe_sse_http(
    url: str,
    *,
    auth_token: str | None = None,
    timeout_s: float = 8.0,
) -> ConnectionProbeResult:
    """Verify a remote MCP-over-HTTP/SSE endpoint is reachable.

    First attempts a real MCP ``initialize`` POST (:func:`_try_mcp_initialize`):
    a verified ``serverInfo`` response is a definitive pass and a 401/403 is a
    definitive auth failure. Only when that handshake is *inconclusive* does it
    fall back to the lenient GET reachability probe below, which issues an HTTP
    GET with ``Accept: text/event-stream, application/json`` (the two content
    types MCP-over-HTTP servers negotiate). The server may respond with any of:
      * 200 — fully reachable + likely speaks MCP
      * 401/403 — reachable but auth failed (still counts as "reachable",
                  the user just needs the right token)
      * 404/405 — reachable but the URL path is wrong (counted as reachable
                  with a hint)
      * 406 — reachable + MCP-shaped, but the probe's GET handshake doesn't
              match what the server expects (e.g. FastMCP streamable-http
              only handles POST initialize). Treated as a soft pass.
      * 415 — reachable + MCP-shaped, same root cause as 406 ("Unsupported
              Media Type" on a POST-only route). Soft pass.
      * 400 — FastMCP streamable-http rejects a session-less GET with a
              JSON-RPC "Missing session ID" error + an mcp-session-id
              header. MCP-shaped 400s are a soft pass; bare 400s fail.
      * connection refused / timeout — server unreachable
    """
    # Catch corrupt URLs (control chars from a bad paste) before httpx raises a
    # cryptic InvalidURL — gives the user a precise, actionable message instead.
    bad_url = _check_url_printable(url)
    if bad_url is not None:
        return bad_url

    # A real initialize handshake is the only thing that proves both "speaks
    # MCP" and "accepts this token". Try it first; fall back when inconclusive.
    decisive = _try_mcp_initialize(url, auth_token=auth_token, timeout_s=timeout_s)
    if decisive is not None:
        return decisive

    try:
        import httpx
    except ImportError:
        return ConnectionProbeResult(
            ok=False,
            transport="sse-http",
            error="httpx not installed",
            hint=(
                "Install via: pip install httpx. Or use the standard install: "
                "pip install quad-mcp-client"
            ),
        )

    headers: dict[str, str] = {
        # MCP-over-HTTP servers (FastMCP streamable-http, etc.) require an
        # Accept header naming at least one of SSE or JSON. Without it many
        # servers respond 406 Not Acceptable to a probe GET.
        "Accept": "text/event-stream, application/json",
    }
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    start = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout_s, follow_redirects=False) as client:
            response = client.get(url, headers=headers)
        elapsed = (time.perf_counter() - start) * 1000.0
    except httpx.ConnectError as e:
        return ConnectionProbeResult(
            ok=False,
            transport="sse-http",
            error=f"connection refused: {e}",
            hint=(
                f"Could not connect to {url}. Check the server is running, "
                "the URL is correct (scheme + host + port), and any firewall "
                "rules allow your IP."
            ),
        )
    except httpx.TimeoutException:
        return ConnectionProbeResult(
            ok=False,
            transport="sse-http",
            latency_ms=timeout_s * 1000.0,
            error=f"connection timed out after {timeout_s}s",
            hint=(
                f"Server at {url} did not respond within {timeout_s}s. "
                "Check it's running and reachable from this network."
            ),
        )
    except Exception as e:
        return ConnectionProbeResult(
            ok=False,
            transport="sse-http",
            error=f"{type(e).__name__}: {e}",
            hint="See error above. Run the request manually with curl to debug.",
        )

    code = response.status_code
    server_header = response.headers.get("server", "")
    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()

    if 200 <= code < 300:
        # Validate this is actually an SSE / MCP endpoint, not a static
        # web page that happens to live at the same URL. MCP-over-HTTP
        # servers respond with `text/event-stream` (SSE) or
        # `application/json` (JSON-RPC over HTTP). A `text/html` 200 is
        # almost certainly the wrong URL.
        if content_type == "text/event-stream":
            return ConnectionProbeResult(
                ok=True,
                transport="sse-http",
                latency_ms=elapsed,
                details={
                    "status_code": code,
                    "server": server_header,
                    "content_type": content_type,
                    "handshake": "sse",
                },
            )
        if content_type in ("application/json", "application/jsonl",
                            "application/x-ndjson"):
            return ConnectionProbeResult(
                ok=True,
                transport="sse-http",
                latency_ms=elapsed,
                details={
                    "status_code": code,
                    "server": server_header,
                    "content_type": content_type,
                    "handshake": "json",
                },
            )
        # 200 OK with a definitively-wrong content-type (HTML page, plain
        # text, etc.) almost certainly means the URL points at a static
        # site — not an MCP endpoint. Reject it.
        if content_type in ("text/html", "text/plain", "text/css",
                            "application/xhtml+xml"):
            return ConnectionProbeResult(
                ok=False,
                transport="sse-http",
                latency_ms=elapsed,
                error=f"HTTP 200 but unexpected content-type: {content_type}",
                hint=(
                    f"Got HTTP 200 from {url} but the server returned {content_type}. "
                    "MCP-over-HTTP servers respond with text/event-stream (SSE) or "
                    "application/json. The URL probably points at a static page — "
                    "check the path (typically /sse or /mcp) or test manually with: "
                    f"curl -i -H 'Accept: text/event-stream' {url}"
                ),
                details={
                    "status_code": code,
                    "server": server_header,
                    "content_type": content_type,
                },
            )
        # No content-type or an unrecognised one — accept reachability but
        # flag the handshake as unverified so callers / docs can show a soft
        # warning.
        return ConnectionProbeResult(
            ok=True,
            transport="sse-http",
            latency_ms=elapsed,
            details={
                "status_code": code,
                "server": server_header,
                "content_type": content_type,
                "handshake": "unverified",
            },
        )

    if code in (401, 403):
        return ConnectionProbeResult(
            ok=False,
            transport="sse-http",
            latency_ms=elapsed,
            error=f"auth failed: HTTP {code}",
            hint=(
                "Server is reachable but the auth token was rejected. "
                "Check the bearer token / cookies / API key for your provider."
            ),
            details={"status_code": code, "server": server_header},
        )

    if code in (404, 405):
        return ConnectionProbeResult(
            ok=False,
            transport="sse-http",
            latency_ms=elapsed,
            error=f"endpoint not found: HTTP {code}",
            hint=(
                f"Server is reachable but {url} returned {code}. "
                "Check the URL path - MCP servers typically expose /sse, /mcp, or /."
            ),
            details={"status_code": code, "server": server_header},
        )

    if code in (406, 415):
        # MCP-over-HTTP servers (FastMCP streamable-http) reject a plain
        # GET probe -- they expect a POST `initialize` JSON-RPC call with
        # a JSON body, not a bare GET. Depending on the framework version
        # this surfaces as:
        #   * 406 — "Not Acceptable" (Accept header mismatch on POST-only route)
        #   * 415 — "Unsupported Media Type"
        # Both are MCP-shaped reachability signals: the URL points at a
        # real MCP endpoint, it just won't talk to a GET handshake. The
        # real client (Claude Code, opencode) does the proper POST and
        # works fine -- so we soft-pass here instead of blocking install.
        # 400 is handled separately below (it requires an MCP-shaped body
        # to soft-pass, since unrelated services also use 400).
        return ConnectionProbeResult(
            ok=True,
            transport="sse-http",
            latency_ms=elapsed,
            details={
                "status_code": code,
                "server": server_header,
                "content_type": content_type,
                "handshake": f"unverified-{code}",
            },
        )

    if code == 400:
        # FastMCP streamable-http rejects a session-less GET with
        # 400 Bad Request + a JSON-RPC "Missing session ID" error and an
        # `mcp-session-id` response header. That's a definitive MCP-server
        # signature -- the real client will open a proper POST session.
        # Treat it as reachable, but ONLY when the response is MCP-shaped;
        # a bare 400 from some unrelated service stays a failure.
        body = (response.text or "").lower()
        mcp_shaped = (
            "mcp-session-id" in response.headers
            or "jsonrpc" in body
            or "session id" in body
        )
        if mcp_shaped:
            return ConnectionProbeResult(
                ok=True,
                transport="sse-http",
                latency_ms=elapsed,
                details={
                    "status_code": code,
                    "server": server_header,
                    "content_type": content_type,
                    "handshake": "unverified-400",
                },
            )

    return ConnectionProbeResult(
        ok=False,
        transport="sse-http",
        latency_ms=elapsed,
        error=f"HTTP {code}",
        hint=f"Server responded with an unexpected status. Check {url} manually.",
        details={"status_code": code, "server": server_header},
    )


# --- Public dispatch -------------------------------------------------------


def probe(
    transport: Transport,
    /,
    **kwargs: Any,
) -> ConnectionProbeResult:
    """Dispatch to the appropriate probe based on transport type."""
    if transport == "stdio-local":
        return probe_stdio_local(**kwargs)
    if transport == "stdio-ssh":
        return probe_stdio_ssh(**kwargs)
    if transport == "sse-http":
        return probe_sse_http(**kwargs)
    return ConnectionProbeResult(
        ok=False,
        transport=transport,  # type: ignore[arg-type]
        error=f"Unknown transport: {transport!r}",
        hint="Supported transports: stdio-local, stdio-ssh, sse-http",
    )
