"""Manage Claude Code skill files (``.claude/skills/*.md``).

Skills are bundled inside the Python package (under
``quad_mcp_client/claude_code/skills_content/``) so a ``pip install``
includes them. ``install_skills`` copies them to the user's
``.claude/skills/`` directory.
"""

from __future__ import annotations

import importlib.resources
import shutil
from pathlib import Path


def bundled_skills_dir() -> Path:
    """Locate the bundled skills directory inside the installed package.

    Falls back to the source-tree location when running in editable mode
    or directly from a checkout.
    """
    # Try the package-internal directory first (set by hatch's force-include
    # equivalent at install time)
    try:
        with importlib.resources.path(
            "quad_mcp_client.claude_code", "skills_content"
        ) as p:
            if p.is_dir():
                return p
    except (ModuleNotFoundError, FileNotFoundError):
        pass

    # Source-tree fallback
    here = Path(__file__).resolve().parent
    candidate = here / "skills_content"
    if candidate.is_dir():
        return candidate

    raise FileNotFoundError(
        "Could not locate the bundled skills directory. Expected at "
        "quad_mcp_client/claude_code/skills_content/. If installed via pip, "
        "ensure the package was built with the skills_content directory "
        "included."
    )


def list_bundled_skills() -> list[Path]:
    """Return the list of bundled ``*.md`` skill files."""
    return sorted(bundled_skills_dir().glob("*.md"))


def install_skills(
    target_dir: Path,
    *,
    force: bool = False,
) -> tuple[list[Path], list[Path]]:
    """Copy bundled skill files into ``target_dir`` in BOTH supported layouts.

    Modern Claude Code (>= late 2025) loads skills from the directory
    form ``<name>/SKILL.md``; older versions and some CLIs read the flat
    ``<name>.md``. We write both so the same content is served regardless
    of which layout the host prefers. If only the flat .md were written,
    a Claude Code that prefers the directory form would silently keep
    serving a stale ``<name>/SKILL.md`` left over from a previous install
    (this caused a real bug on 2026-05-18 where rewired skills appeared
    to "do nothing").

    Args:
        target_dir: typically ``<project_root>/.claude/skills/``
        force: overwrite existing files of the same name. When False,
            existing files are left untouched and listed in the
            ``skipped`` return.

    Returns:
        ``(written, skipped)`` — both lists of Path objects in target_dir.
        Each bundled source maps to up to two output paths (flat + dir).
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    skipped: list[Path] = []
    for src in list_bundled_skills():
        flat_dst = target_dir / src.name
        dir_dst = target_dir / src.stem / "SKILL.md"
        for dst in (flat_dst, dir_dst):
            if dst.exists() and not force:
                skipped.append(dst)
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            written.append(dst)
    return written, skipped


def uninstall_skills(target_dir: Path) -> list[Path]:
    """Remove the bundled skill files from ``target_dir``.

    Removes both the flat ``<name>.md`` and the directory-form
    ``<name>/SKILL.md`` (and the now-empty parent directory). Leaves
    user-added skills alone.
    """
    if not target_dir.is_dir():
        return []
    bundled_stems = {p.stem for p in list_bundled_skills()}
    removed: list[Path] = []
    for f in target_dir.glob("*.md"):
        if f.stem in bundled_stems:
            f.unlink()
            removed.append(f)
    for stem in bundled_stems:
        skill_md = target_dir / stem / "SKILL.md"
        if skill_md.is_file():
            skill_md.unlink()
            removed.append(skill_md)
            try:
                skill_md.parent.rmdir()
            except OSError:
                pass  # directory not empty -> user added their own files; leave it
    return removed


def list_installed_skills(target_dir: Path) -> list[Path]:
    """Return one entry per installed skill (deduped across flat + dir forms).

    When both ``<name>.md`` and ``<name>/SKILL.md`` exist (the install_skills
    dual-write), only the flat form is returned. Caller-facing counts treat
    one logical skill as one entry, regardless of layout on disk.
    """
    if not target_dir.is_dir():
        return []
    seen_stems: set[str] = set()
    entries: list[Path] = []
    for f in sorted(target_dir.glob("*.md")):
        seen_stems.add(f.stem)
        entries.append(f)
    for skill_md in sorted(target_dir.glob("*/SKILL.md")):
        stem = skill_md.parent.name
        if stem not in seen_stems:
            seen_stems.add(stem)
            entries.append(skill_md)
    return entries
