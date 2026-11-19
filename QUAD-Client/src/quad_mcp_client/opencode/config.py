"""Generate ``opencode.json`` for the QUAD MCP server.

opencode is the second supported coding agent (alongside Claude Code).
Unlike Claude Code it does **not** read ``.claude/settings.json`` — it
discovers MCP servers from ``opencode.json`` (top-level ``mcp`` key) and
auto-discovers skills from ``.claude/skills/**/SKILL.md`` natively. So
the only thing the QUAD opencode integration has to write is the MCP
block (plus an ``instructions`` pointer at the existing ``CLAUDE.md``);
the skills are reused verbatim from the same ``.claude/skills`` directory
Claude Code uses.

This module is the single source of truth for the opencode config shape.
It translates the shared :class:`TransportConfig` (defined alongside the
Claude Code provisioner) rather than re-deriving how the server is
launched, so there is exactly one place that knows "how to start
``quad.mcp.server``".

Schema reference: https://opencode.ai/config.json (verified against the
bundled opencode v1.17.5 config schema — ``mcp.<name>`` is one of
``{type:"local", command:[…], environment:{…}}`` or
``{type:"remote", url, headers}``; ``instructions`` is an array of paths).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quad_mcp_client.claude_code.provisioner import TransportConfig

OPENCODE_SCHEMA = "https://opencode.ai/config.json"

# opencode reads ambient project instructions from these paths. We reuse
# the CLAUDE.md that already ships in each repo rather than maintaining a
# second AGENTS.md.
DEFAULT_INSTRUCTIONS: tuple[str, ...] = ("CLAUDE.md",)


def opencode_mcp_block(tc: TransportConfig) -> dict[str, Any]:
    """Translate a :class:`TransportConfig` into an opencode ``mcp`` entry.

    Returns the value for ``opencode.json`` ``mcp.quad``. The three QUAD
    transports map onto opencode's two MCP connection types:

    * ``stdio-local`` -> ``type: local`` spawning ``quad.mcp.server``
      directly. ``environment`` carries ``QUAD_ADAPTER_MODE``. No ``cwd``
      is set so opencode defaults it to the workspace directory.
    * ``stdio-ssh``   -> ``type: local`` whose command is the ``ssh``
      invocation that proxies stdio to the remote server (same arg shape
      as the Claude Code SSH settings).
    * ``sse-http``    -> ``type: remote`` with the SSE URL and optional
      bearer-token header.
    """
    if tc.transport == "stdio-local":
        return {
            "type": "local",
            "command": [tc.server_command, *tc.server_args],
            "environment": {"QUAD_ADAPTER_MODE": tc.adapter_mode},
        }
    if tc.transport == "stdio-ssh":
        command: list[str] = ["ssh", "-p", str(tc.ssh_port)]
        if tc.ssh_key:
            command += ["-i", tc.ssh_key]
        command += [
            "-o",
            "BatchMode=yes",
            "-o",
            "ServerAliveInterval=30",
            f"{tc.ssh_user}@{tc.ssh_host}",
            tc.ssh_server_command,
        ]
        return {"type": "local", "command": command}
    if tc.transport == "sse-http":
        block: dict[str, Any] = {"type": "remote", "url": tc.sse_url}
        if tc.sse_auth_token_env:
            block["headers"] = {
                "Authorization": f"Bearer ${{env:{tc.sse_auth_token_env}}}",
            }
        return block
    raise ValueError(f"Unknown transport: {tc.transport!r}")


def opencode_config(
    transport_config: TransportConfig,
    *,
    instructions: tuple[str, ...] | list[str] = DEFAULT_INSTRUCTIONS,
) -> dict[str, Any]:
    """Build the full ``opencode.json`` document for the QUAD server.

    Args:
        transport_config: how opencode reaches the QUAD MCP server.
        instructions: ambient-instruction file paths opencode should
            load (default: the project ``CLAUDE.md``).
    """
    return {
        "$schema": OPENCODE_SCHEMA,
        "mcp": {"quad": opencode_mcp_block(transport_config)},
        "instructions": list(instructions),
    }


def render_to_json(config: dict[str, Any], *, indent: int = 2) -> str:
    """Serialise the config to JSON with a trailing newline."""
    return json.dumps(config, indent=indent) + "\n"


def merge_config(existing: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
    """Merge QUAD's generated config into a user's existing ``opencode.json``.

    The user may already have an ``opencode.json`` with providers, models,
    or other MCP servers. We must not clobber those — only set the
    ``$schema`` (if absent), our own ``mcp.quad`` entry, and union the
    ``instructions`` list. Everything else is left untouched.
    """
    merged = dict(existing)
    merged.setdefault("$schema", generated["$schema"])

    mcp = dict(merged.get("mcp") or {})
    mcp["quad"] = generated["mcp"]["quad"]
    merged["mcp"] = mcp

    existing_instructions = list(merged.get("instructions") or [])
    for path in generated.get("instructions", []):
        if path not in existing_instructions:
            existing_instructions.append(path)
    if existing_instructions:
        merged["instructions"] = existing_instructions

    return merged


def write_config(
    path: Path,
    *,
    config: dict[str, Any],
    force: bool = False,
    merge: bool = False,
) -> bool:
    """Write/merge ``opencode.json``. Returns True if the file was written.

    If the file already exists, QUAD's ``mcp.quad`` block (and the schema /
    instructions) are merged in non-destructively — the rest of the user's
    config is preserved. ``force`` and ``merge`` both suppress the "already
    has an mcp.quad entry, skipping" short-circuit so a re-run *refreshes* the
    ``quad`` block (e.g. a changed server URL or token env) while still keeping
    the user's other providers/models/MCP servers; the merge itself is
    identical, so neither one blindly overwrites the file. ``merge`` is the
    signal used when the caller supplied explicit server details, mirroring
    ``write_settings(merge=True)`` on the Claude Code side. When the file does
    not exist it is created from ``config``.
    """
    if path.exists():
        try:
            existing = json.loads(path.read_text())
            if not isinstance(existing, dict):
                existing = {}
        except (json.JSONDecodeError, OSError):
            existing = {}
        # Already provisioned and neither forcing nor refreshing -> no-op.
        if (
            not force
            and not merge
            and isinstance(existing.get("mcp"), dict)
            and "quad" in existing["mcp"]
        ):
            return False
        config = merge_config(existing, config)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_to_json(config))
    return True
