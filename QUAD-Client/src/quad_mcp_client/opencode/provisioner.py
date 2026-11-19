"""Concrete :class:`MCPClientProvisioner` for opencode.

opencode reuses Claude Code's on-disk skill files: it natively
auto-discovers ``<project>/.claude/skills/**/SKILL.md`` (verified against
opencode v1.17.5). Those skills load as *model-invoked tools* — opencode
picks one by its ``description`` when the user asks in natural language.
They do **not** appear in the ``/`` slash menu; that menu is populated by
*commands* (``.opencode/commands/<name>.md``). So this provisioner:

1. Writes/merges ``opencode.json`` (the MCP server block + an
   ``instructions`` pointer at ``CLAUDE.md``).
2. Makes sure the skill files exist on disk in the directory form opencode
   globs for — by delegating to the *same* skill installer the Claude Code
   provisioner uses. There is no opencode-specific copy of any skill; update
   a ``SKILL.md`` once and both agents see it.
3. Generates one thin ``.opencode/commands/<skill>.md`` per skill so opencode
   users get the same ``/quad-detect`` slash commands Claude Code exposes.
   Each command body just invokes its skill, so the ``SKILL.md`` stays the
   single source of truth.

Layout under ``project_root``::

    opencode.json          # MCP server discovery + instructions
    .claude/skills/
    ├── quad-detect.md          # flat form (Claude Code <= legacy)
    ├── quad-detect/SKILL.md    # dir form  (Claude Code modern + opencode)
    └── …
    .opencode/commands/
    ├── quad-detect.md          # slash command -> invokes the quad-detect skill
    └── …

MCP tools are discovered dynamically by opencode at runtime, so adding a
tool to ``quad.mcp.server`` needs no reprovisioning either.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quad_mcp_client import MCPClientProvisioner, ProvisionResult
from quad_mcp_client.claude_code.provisioner import TransportConfig
from quad_mcp_client.claude_code.skills import (
    install_skills,
    list_bundled_skills,
    list_installed_skills,
)
from quad_mcp_client.opencode.commands import remove_commands, write_commands
from quad_mcp_client.opencode.config import (
    DEFAULT_INSTRUCTIONS,
    opencode_config,
    write_config,
)

CONFIG_FILE = "opencode.json"
CLAUDE_DIR_NAME = ".claude"
SKILLS_DIR = "skills"


class OpenCodeProvisioner(MCPClientProvisioner):
    """Install + manage opencode's QUAD MCP integration.

    ``install`` is idempotent: re-running merges QUAD's ``mcp.quad`` block
    into any existing ``opencode.json`` without clobbering the user's other
    settings, and skips skill files that already exist unless ``force=True``.
    """

    name = "opencode"

    def install(
        self,
        project_root: Path,
        *,
        force: bool = False,
        adapter_mode: str = "real",
        transport_config: TransportConfig | None = None,
    ) -> ProvisionResult:
        """Install opencode config + ensure the shared skills are on disk.

        Args:
            project_root: directory under which ``opencode.json`` is created
                and where ``.claude/skills/`` is (re)materialised.
            force: re-merge ``opencode.json`` even if already provisioned, and
                overwrite existing skill files.
            adapter_mode: ``mock`` or ``real`` — used only when
                ``transport_config`` is not given (builds a stdio-local config).
            transport_config: full transport spec; defaults to stdio-local
                with ``adapter_mode``.
        """
        # An explicit transport_config means the user supplied server details
        # (URL, token, ssh target); a re-run should then REFRESH mcp.quad even
        # without --force. A bare install (defaulted to stdio-local below) keeps
        # the safe skip-if-already-provisioned behaviour.
        explicit_details = transport_config is not None
        if transport_config is None:
            transport_config = TransportConfig(
                transport="stdio-local", adapter_mode=adapter_mode
            )

        config_path = project_root / CONFIG_FILE
        skills_target = project_root / CLAUDE_DIR_NAME / SKILLS_DIR

        result = ProvisionResult(
            client=self.name,
            settings_path=str(config_path),
            skills_dir=str(skills_target),
        )

        # 1. opencode.json — MCP server + instructions (non-destructive merge)
        config = opencode_config(transport_config, instructions=DEFAULT_INSTRUCTIONS)
        preexisting = config_path.exists()
        if write_config(config_path, config=config, force=force, merge=explicit_details):
            result.files_written.append(str(config_path))
            if explicit_details and not force and preexisting:
                result.notes.append(
                    f"opencode.json updated: refreshed mcp.quad "
                    f"({transport_config.transport}) — other config preserved."
                )
        else:
            result.files_skipped.append(str(config_path))
            result.notes.append(
                f"opencode.json already has an mcp.quad entry — pass force=True "
                f"to re-merge. Read at: {config_path}"
            )

        # 2. Skills — reuse the exact files Claude Code uses. install_skills
        #    dual-writes flat + <name>/SKILL.md; opencode globs the dir form.
        try:
            written, skipped = install_skills(skills_target, force=force)
            result.files_written.extend(str(p) for p in written)
            result.files_skipped.extend(str(p) for p in skipped)
            if skipped and not force:
                result.notes.append(
                    f"{len(skipped)} skill file(s) already exist — pass force=True to overwrite."
                )
        except FileNotFoundError as e:
            result.notes.append(f"Skill installation failed: {e}")

        # 3. Slash commands — one .opencode/commands/<skill>.md per skill so the
        #    /quad-* commands show up in opencode's slash menu (skills alone are
        #    model-invoked tools and do NOT appear there).
        try:
            cmd_written, cmd_skipped = write_commands(project_root, force=force)
            result.files_written.extend(str(p) for p in cmd_written)
            result.files_skipped.extend(str(p) for p in cmd_skipped)
            if cmd_skipped and not force:
                result.notes.append(
                    f"{len(cmd_skipped)} opencode command file(s) already exist — "
                    f"pass force=True to overwrite."
                )
        except FileNotFoundError as e:
            result.notes.append(f"opencode command generation failed: {e}")

        result.notes.append(
            "opencode loads skills from .claude/skills/**/SKILL.md (model-invoked "
            "when you ask in natural language) and the matching /quad-* slash "
            "commands from .opencode/commands/. MCP tools are discovered from "
            "quad.mcp.server at runtime — skill/tool updates need no reprovisioning."
        )
        return result

    def uninstall(self, project_root: Path) -> ProvisionResult:
        """Remove ``opencode.json`` only.

        The ``.claude/skills`` directory is shared with the Claude Code
        provisioner, so it is deliberately left in place — uninstall it via
        ``--client claude_code`` if desired.
        """
        config_path = project_root / CONFIG_FILE
        skills_target = project_root / CLAUDE_DIR_NAME / SKILLS_DIR

        result = ProvisionResult(
            client=self.name,
            settings_path=str(config_path),
            skills_dir=str(skills_target),
        )

        if config_path.is_file():
            config_path.unlink()
            result.files_written.append(str(config_path))  # 'removed' for the report
            result.notes.append(f"Removed {config_path}.")
        else:
            result.notes.append(f"No opencode.json found at {config_path}.")

        # Remove the generated slash commands (leaves user-authored ones).
        removed_cmds = remove_commands(project_root)
        result.files_written.extend(str(p) for p in removed_cmds)
        if removed_cmds:
            result.notes.append(
                f"Removed {len(removed_cmds)} generated .opencode/commands/ file(s)."
            )

        result.notes.append(
            ".claude/skills was NOT removed (shared with Claude Code). "
            "Use --client claude_code to remove bundled skills."
        )
        return result

    def status(self, project_root: Path) -> dict[str, Any]:
        config_path = project_root / CONFIG_FILE
        skills_target = project_root / CLAUDE_DIR_NAME / SKILLS_DIR

        installed_skills = list_installed_skills(skills_target)
        bundled = {p.stem for p in list_bundled_skills()}
        # list_installed_skills returns either a flat <name>.md or a
        # <name>/SKILL.md path; resolve the skill name from each.
        installed_names = {
            p.parent.name if p.name == "SKILL.md" else p.stem for p in installed_skills
        }
        missing = sorted(bundled - installed_names)
        extra = sorted(installed_names - bundled)

        return {
            "client": self.name,
            "settings_path": str(config_path),
            "settings_exists": config_path.is_file(),
            "skills_dir": str(skills_target),
            "skills_dir_exists": skills_target.is_dir(),
            "bundled_skill_count": len(bundled),
            "installed_skill_count": len(installed_skills),
            "missing_skills": missing,
            "extra_user_skills": extra,
        }

    def render_config_preview(
        self,
        *,
        transport_config: TransportConfig | None = None,
    ) -> str:
        """Return the JSON content that ``install()`` would write (fresh file)."""
        from quad_mcp_client.opencode.config import render_to_json

        if transport_config is None:
            transport_config = TransportConfig(transport="stdio-local")
        return render_to_json(opencode_config(transport_config))
