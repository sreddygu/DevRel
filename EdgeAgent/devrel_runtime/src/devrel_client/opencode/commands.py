"""Generate opencode slash commands from the bundled DevRel skills.

In opencode, *skills* (``.claude/skills/<name>/SKILL.md``) are loaded as
model-invoked tools — the model picks one based on its ``description`` when
the user asks in natural language. They do **not** appear in the ``/`` menu.
The ``/`` menu is populated by *commands*: ``.opencode/commands/<name>.md``
files, each a reusable prompt (opencode v1.17.5, verified against the schema
``ConfigCommandV1 = {template, description}``).

To give opencode users the same ``/devrel-detect`` muscle memory Claude Code
users have, we generate one thin command per skill. Each command's body just
tells the model to invoke the matching skill, so there is a single source of
truth — the ``SKILL.md`` — and the command is a 3-line shim that never drifts.
"""

from __future__ import annotations

from pathlib import Path

from devrel_client.claude_code.skills import list_bundled_skills

COMMANDS_DIR = Path(".opencode") / "commands"


def _parse_frontmatter(md_text: str) -> dict[str, str]:
    """Extract ``name`` and ``description`` from a skill's YAML frontmatter.

    Deliberately dependency-free (no PyYAML): skills use simple single-line
    ``key: value`` frontmatter, so a line scan between the ``---`` fences is
    enough and avoids adding a runtime dep to the lightweight client.
    """
    fields: dict[str, str] = {}
    lines = md_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return fields
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith((" ", "\t")) or ":" not in line:
            continue  # nested/multi-line value — skip; we only need top-level
        key, _, value = line.partition(":")
        key = key.strip()
        if key in ("name", "description"):
            fields[key] = value.strip().strip('"').strip("'")
    return fields


def _short_description(description: str, skill_name: str) -> str:
    """Condense a skill's long trigger-phrase description to a menu label.

    Skill descriptions are written for model routing ("Use when the user asks
    …, or invokes /devrel-detect. <what it does>"). For the slash menu we want
    the *what it does* part: drop a leading "Use when …" trigger clause if a
    following sentence exists, then take the first sentence.
    """
    text = " ".join((description or "").split())
    if not text:
        return f"Run the {skill_name} skill."
    # Split into sentences; drop a leading "Use when …/invokes …" trigger
    # sentence when there's a real description after it.
    parts = [p.strip() for p in text.split(". ") if p.strip()]
    if len(parts) > 1 and parts[0].lower().startswith(("use when", "use this")):
        parts = parts[1:]
    short = parts[0].rstrip(".")
    # Keep menu labels readable.
    if len(short) > 100:
        short = short[:97].rstrip() + "…"
    return short + "."


def command_body(skill_name: str, description: str) -> str:
    """Render the markdown body for a single ``.opencode/commands`` file."""
    desc_one_line = _short_description(description, skill_name)
    return (
        f"---\n"
        f"description: {desc_one_line}\n"
        f"---\n"
        f"Use the `{skill_name}` skill to handle this request. "
        f"Follow the skill's instructions exactly. $ARGUMENTS\n"
    )


def write_commands(
    project_root: Path,
    *,
    force: bool = False,
) -> tuple[list[Path], list[Path]]:
    """Write one ``.opencode/commands/<skill>.md`` per bundled skill.

    Args:
        project_root: repo root; commands are written under
            ``project_root/.opencode/commands/``.
        force: overwrite existing command files. When False, existing files
            are left untouched and returned in ``skipped``.

    Returns:
        ``(written, skipped)`` lists of Path objects.
    """
    target = project_root / COMMANDS_DIR
    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    skipped: list[Path] = []
    for src in list_bundled_skills():
        fm = _parse_frontmatter(src.read_text(encoding="utf-8"))
        name = fm.get("name") or src.stem
        dst = target / f"{name}.md"
        if dst.exists() and not force:
            skipped.append(dst)
            continue
        dst.write_text(command_body(name, fm.get("description", "")), encoding="utf-8")
        written.append(dst)
    return written, skipped


def remove_commands(project_root: Path) -> list[Path]:
    """Remove generated ``.opencode/commands/<skill>.md`` files.

    Only removes files whose stem matches a bundled skill name, leaving any
    user-authored commands in place. Cleans up the now-empty directory.
    """
    target = project_root / COMMANDS_DIR
    if not target.is_dir():
        return []
    bundled_names = {
        (_parse_frontmatter(p.read_text(encoding="utf-8")).get("name") or p.stem)
        for p in list_bundled_skills()
    }
    removed: list[Path] = []
    for name in bundled_names:
        f = target / f"{name}.md"
        if f.is_file():
            f.unlink()
            removed.append(f)
    try:
        target.rmdir()  # only succeeds if empty (no user commands left)
    except OSError:
        pass
    return removed
