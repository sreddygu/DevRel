"""Concrete :class:`MCPClientProvisioner` for Claude Code."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from devrel_client import MCPClientProvisioner, ProvisionResult
from devrel_client.claude_code.settings import (
    DEFAULT_PERMISSIONS,
    build_settings,
    render_to_json,
    settings_template,  # noqa: F401  (re-exported for legacy callers)
    settings_template_sse,
    settings_template_ssh,
    write_settings,
)
from devrel_client.claude_code.skills import (
    bundled_skills_dir,  # noqa: F401  (re-exported)
    install_skills,
    list_bundled_skills,
    list_installed_skills,
    uninstall_skills,
)

CLAUDE_DIR_NAME = ".claude"
SETTINGS_FILE = "settings.json"
SKILLS_DIR = "skills"


Transport = Literal["stdio-local", "stdio-ssh", "sse-http"]


@dataclass
class TransportConfig:
    """Where the MCP server lives + how Claude Code reaches it."""

    transport: Transport = "stdio-local"

    # stdio-local
    server_command: str = "python"
    # ``-u`` is load-bearing on Windows: without unbuffered Python the
    # MCP server's JSON-RPC responses sit in the block-buffered stdout
    # pipe (~8 KB) and Claude Code's stdio client never sees them.
    server_args: list[str] = field(default_factory=lambda: ["-u", "-m", "devrel.mcp.server"])
    cwd: str = "${workspaceFolder}"

    # stdio-ssh
    ssh_user: str = ""
    ssh_host: str = ""
    ssh_port: int = 22
    ssh_key: str | None = None
    ssh_server_command: str = "python -m devrel.mcp.server"

    # sse-http
    sse_url: str = ""
    sse_auth_token_env: str | None = None

    # common
    adapter_mode: str = "mock"
    permissions: tuple[str, ...] = DEFAULT_PERMISSIONS

    def to_settings(self) -> dict[str, Any]:
        """Render the appropriate settings.json shape for this transport."""
        if self.transport == "stdio-local":
            return settings_template(
                server_command=self.server_command,
                server_args=self.server_args,
                cwd=self.cwd,
                adapter_mode=self.adapter_mode,
                permissions=self.permissions,
            )
        if self.transport == "stdio-ssh":
            return settings_template_ssh(
                ssh_user=self.ssh_user,
                ssh_host=self.ssh_host,
                ssh_port=self.ssh_port,
                ssh_key=self.ssh_key,
                server_command=self.ssh_server_command,
                permissions=self.permissions,
            )
        if self.transport == "sse-http":
            return settings_template_sse(
                url=self.sse_url,
                auth_token_env=self.sse_auth_token_env,
                permissions=self.permissions,
            )
        raise ValueError(f"Unknown transport: {self.transport!r}")


class ClaudeCodeProvisioner(MCPClientProvisioner):
    """Install + manage Claude Code's DevRel MCP integration.

    Layout under ``project_root``::

        .claude/
        ├── settings.json   # MCP server discovery + tool permissions
        └── skills/
            ├── devrel-quickstart.md
            ├── devrel-detect.md
            └── …

    ``install`` is idempotent: re-running on an already-provisioned
    project skips files that exist, unless ``force=True``.
    """

    name = "claude_code"

    def install(
        self,
        project_root: Path,
        *,
        force: bool = False,
        adapter_mode: str = "mock",
        permissions: tuple[str, ...] | None = None,
        transport_config: TransportConfig | None = None,
    ) -> ProvisionResult:
        """Install Claude Code config + skills.

        Args:
            project_root: directory under which ``.claude/`` is created
            force: overwrite existing settings.json + skills
            adapter_mode: ``mock`` or ``real`` (only used for stdio-local)
            permissions: pre-approved MCP tool names
            transport_config: full transport spec; if None, defaults to
                stdio-local with ``adapter_mode``. For SSH/SSE servers,
                the caller MUST pass an explicit TransportConfig.
        """
        claude_dir = project_root / CLAUDE_DIR_NAME
        settings_path = claude_dir / SETTINGS_FILE
        skills_target = claude_dir / SKILLS_DIR

        result = ProvisionResult(
            client=self.name,
            settings_path=str(settings_path),
            skills_dir=str(skills_target),
        )

        # 1. settings.json — pick the shape based on transport
        if transport_config is None:
            settings = build_settings(
                adapter_mode=adapter_mode,
                permissions=permissions or DEFAULT_PERMISSIONS,
            )
        else:
            settings = transport_config.to_settings()

        # When the user supplied explicit server details we MERGE the freshly
        # built ``devrel`` block into any existing settings.json (preserving the
        # user's other mcpServers / permissions / custom keys) instead of
        # skipping the whole file. A bare install (no transport_config) keeps
        # the safe skip-unless-force behaviour so a no-arg re-run is a no-op.
        merge = transport_config is not None
        preexisting = settings_path.exists()
        settings_written = write_settings(
            settings_path, settings=settings, force=force, merge=merge
        )
        if settings_written:
            result.files_written.append(str(settings_path))
            if merge and not force and preexisting:
                devrel_block = settings.get("mcpServers", {}).get("devrel", {})
                ttype = devrel_block.get("transport", {}).get("type")
                detail = f" (transport={ttype})" if ttype else ""
                result.notes.append(
                    f"settings.json updated: merged mcpServers.devrel{detail} "
                    f"into existing config (other keys preserved)."
                )
        else:
            result.files_skipped.append(str(settings_path))
            result.notes.append(
                f"settings.json already exists — pass force=True to overwrite. "
                f"Read at: {settings_path}"
            )

        # 2. skills
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

        return result

    def uninstall(self, project_root: Path) -> ProvisionResult:
        claude_dir = project_root / CLAUDE_DIR_NAME
        settings_path = claude_dir / SETTINGS_FILE
        skills_target = claude_dir / SKILLS_DIR

        result = ProvisionResult(
            client=self.name,
            settings_path=str(settings_path),
            skills_dir=str(skills_target),
        )

        # Remove bundled skills (leave user-added ones alone)
        try:
            removed = uninstall_skills(skills_target)
            result.files_written = [str(p) for p in removed]  # 'removed' for the report
            result.notes.append(
                f"Removed {len(removed)} bundled skill file(s) from {skills_target}."
            )
        except Exception as e:
            result.notes.append(f"Skill uninstall failed: {e}")

        # Don't auto-delete settings.json — user may have customised it
        if settings_path.exists():
            result.notes.append(
                f"settings.json was NOT removed (may contain user customisations). "
                f"Delete manually if desired: {settings_path}"
            )

        return result

    def status(self, project_root: Path) -> dict[str, Any]:
        claude_dir = project_root / CLAUDE_DIR_NAME
        settings_path = claude_dir / SETTINGS_FILE
        skills_target = claude_dir / SKILLS_DIR

        installed_skills = list_installed_skills(skills_target)
        bundled = {p.name for p in list_bundled_skills()}
        installed_names = {p.name for p in installed_skills}
        missing = sorted(bundled - installed_names)
        extra = sorted(installed_names - bundled)

        return {
            "client": self.name,
            "settings_path": str(settings_path),
            "settings_exists": settings_path.is_file(),
            "skills_dir": str(skills_target),
            "skills_dir_exists": skills_target.is_dir(),
            "bundled_skill_count": len(bundled),
            "installed_skill_count": len(installed_skills),
            "missing_skills": missing,
            "extra_user_skills": extra,
        }

    def render_settings_preview(
        self,
        *,
        adapter_mode: str = "mock",
        permissions: tuple[str, ...] | None = None,
    ) -> str:
        """Return the JSON content that ``install()`` would write.

        Useful for ``devrel-agent preview`` (see CLI), so users can
        inspect before committing.
        """
        return render_to_json(
            build_settings(
                adapter_mode=adapter_mode,
                permissions=permissions or DEFAULT_PERMISSIONS,
            )
        )
