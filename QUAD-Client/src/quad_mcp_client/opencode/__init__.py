"""opencode-specific provisioning for the QUAD MCP server.

Generates ``opencode.json`` (MCP server discovery + an ``instructions``
pointer at ``CLAUDE.md``) and ensures the shared skill files exist under
``.claude/skills/``. opencode auto-discovers those skills natively, so
there is no opencode-specific copy of any skill — the same files Claude
Code uses are reused verbatim.

Public API::

    from quad_mcp_client.opencode import OpenCodeProvisioner
    p = OpenCodeProvisioner()
    p.install(Path.cwd())
    p.status(Path.cwd())
"""

from quad_mcp_client.opencode.config import (
    DEFAULT_INSTRUCTIONS,
    OPENCODE_SCHEMA,
    merge_config,
    opencode_config,
    opencode_mcp_block,
    render_to_json,
    write_config,
)
from quad_mcp_client.opencode.provisioner import OpenCodeProvisioner

__all__ = [
    "OpenCodeProvisioner",
    "OPENCODE_SCHEMA",
    "DEFAULT_INSTRUCTIONS",
    "opencode_config",
    "opencode_mcp_block",
    "merge_config",
    "render_to_json",
    "write_config",
]
