"""QUAD MCP client — IDE / agent-specific provisioning for the QUAD MCP server.

The QUAD MCP server (which lives in the separate ``QUAD`` repository) is
the same regardless of which client (Claude Code, Cursor, Continue, …)
connects to it. What differs per client is **how that client discovers
and authorises the server** — typically via a config file (e.g.
``.claude/settings.json``) and a set of skill / instruction files.

This package isolates that client-specific provisioning so the MCP
server stays generic, and adding support for a new client is a focused
change.

Public abstract base:

    from quad_mcp_client import MCPClientProvisioner

Concrete implementations:

    from quad_mcp_client.claude_code import ClaudeCodeProvisioner

CLI entry point: ``quad-client install [--client claude_code]``.

Three transports are supported for talking to the QUAD MCP server:

* ``stdio-local`` — server + client on the same machine; the client
  spawns the server as a subprocess.
* ``stdio-ssh`` — server runs on a remote machine; the client proxies
  stdio over SSH.
* ``sse-http`` — server runs as a hosted HTTP service speaking MCP
  over Server-Sent Events.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__version__ = "0.2.0"


@dataclass
class ProvisionResult:
    """Result of installing client-side config + skills."""

    client: str
    files_written: list[str] = field(default_factory=list)
    files_skipped: list[str] = field(default_factory=list)
    settings_path: str | None = None
    skills_dir: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "client": self.client,
            "files_written": self.files_written,
            "files_skipped": self.files_skipped,
            "settings_path": self.settings_path,
            "skills_dir": self.skills_dir,
            "notes": self.notes,
        }


class MCPClientProvisioner(ABC):
    """Abstract base for client-side QUAD MCP integrations.

    Subclasses implement how to:
      * Generate the client's config file (e.g. settings.json)
      * Install skill / instruction files into the client's expected
        location
      * Verify an existing install
      * Uninstall

    The MCP server itself is always the same: ``quad.mcp.server``,
    invoked by the client via stdio (or SSH-tunnelled stdio, or
    SSE-over-HTTP).
    """

    name: str = "abstract"

    @abstractmethod
    def install(self, project_root: Path, *, force: bool = False) -> ProvisionResult:
        """Install client config + skills under ``project_root``."""

    @abstractmethod
    def uninstall(self, project_root: Path) -> ProvisionResult:
        """Remove the client config + skills (does not affect the QUAD server)."""

    @abstractmethod
    def status(self, project_root: Path) -> dict[str, Any]:
        """Report what's currently installed under ``project_root``."""


def get_provisioner(client: str = "claude_code") -> MCPClientProvisioner:
    """Factory — returns a provisioner for the given client name."""
    if client == "claude_code":
        from quad_mcp_client.claude_code.provisioner import ClaudeCodeProvisioner

        return ClaudeCodeProvisioner()
    if client == "opencode":
        from quad_mcp_client.opencode.provisioner import OpenCodeProvisioner

        return OpenCodeProvisioner()
    raise ValueError(
        f"Unknown MCP client: {client!r}. Supported: 'claude_code', 'opencode'. "
        "Other clients (cursor, continue, cline) can be added by implementing "
        "MCPClientProvisioner in a new submodule under quad_mcp_client."
    )


def __getattr__(name: str) -> Any:
    """Lazily expose the QuadClient SDK symbols.

    The SDK (``quad_mcp_client.client``) uses fastmcp lazily; importing it
    eagerly here would be fine (fastmcp is only touched on connect), but a
    module-level ``__getattr__`` keeps ``import quad_mcp_client`` cheap and
    avoids importing the SDK module for pure-provisioner callers.
    """
    if name in {
        "QuadClient", "create_client", "RetryPolicy", "ClientAuth",
        "QuadClientError", "QuadToolError", "QuadConnectionError",
    }:
        from quad_mcp_client import client as _client_mod

        return getattr(_client_mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "MCPClientProvisioner",
    "ProvisionResult",
    "get_provisioner",
    # SDK (lazy)
    "QuadClient",
    "create_client",
    "RetryPolicy",
    "ClientAuth",
    "QuadClientError",
    "QuadToolError",
    "QuadConnectionError",
    "__version__",
]
