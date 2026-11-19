"""Claude Code-specific provisioning for the QUAD MCP server.

Generates ``.claude/settings.json`` and installs the bundled skill
files into ``.claude/skills/``. The MCP server itself is unchanged —
this package only handles the *client side* of the integration.

Public API::

    from quad_mcp_client.claude_code import ClaudeCodeProvisioner
    p = ClaudeCodeProvisioner()
    p.install(Path.cwd())
    p.status(Path.cwd())
"""

from quad_mcp_client.claude_code.provisioner import ClaudeCodeProvisioner
from quad_mcp_client.claude_code.settings import (
    DEFAULT_PERMISSIONS,
    build_settings,
    settings_template,
    settings_template_sse,
    settings_template_ssh,
)
from quad_mcp_client.claude_code.skills import (
    bundled_skills_dir,
    install_skills,
    list_bundled_skills,
)

__all__ = [
    "ClaudeCodeProvisioner",
    "DEFAULT_PERMISSIONS",
    "build_settings",
    "settings_template",
    "settings_template_ssh",
    "settings_template_sse",
    "bundled_skills_dir",
    "install_skills",
    "list_bundled_skills",
]
