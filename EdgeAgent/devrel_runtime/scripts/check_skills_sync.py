#!/usr/bin/env python3
"""CI guard: keep skill files in sync across their three on-disk forms.

A skill can exist in up to three places:

* **source**  — ``src/devrel_client/claude_code/skills_content/<name>.md``
  (the pip-bundled canonical copy; the installer ``shutil.copy2``s it verbatim)
* **flat**    — ``.claude/skills/<name>.md``
* **dir**     — ``.claude/skills/<name>/SKILL.md``

The installer is a *pure copy* (no frontmatter rewriting — see
``devrel_client/claude_code/skills.py``), so when a skill is in sync all
present forms are **byte-identical**. They drift when someone edits one copy by
hand; running ``devrel-agent install --force`` then silently reverts the others.
This script fails CI on that drift so "edit the source, regenerate" is enforced
rather than merely documented.

Rules, per skill ``<name>``:

1. flat and dir must both exist and be byte-identical.
2. if a ``skills_content/<name>.md`` source exists, it must equal flat (== dir).
3. a committed-only skill (no source) is allowed **only** if it is on
   ``DEV_ONLY`` — otherwise it should have a source so ``pip install`` ships it.
4. an orphan source (source but no committed flat) is an error.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Skills intentionally committed-only (no skills_content source). The client
# ships every user-facing skill via source, so this is empty today — add a
# name here only for a genuine developer-only skill.
DEV_ONLY: set[str] = set()

REPO = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO / ".claude" / "skills"
SOURCE_DIR = REPO / "src" / "devrel_client" / "claude_code" / "skills_content"


def _read(p: Path) -> bytes:
    return p.read_bytes()


def main() -> int:
    if not SKILLS_DIR.is_dir():
        print(f"SKIP: no skills dir at {SKILLS_DIR}")
        return 0

    errors: list[str] = []

    flat_skills = sorted(SKILLS_DIR.glob("*.md"))
    flat_names = {p.stem for p in flat_skills}

    for flat in flat_skills:
        name = flat.stem
        dir_form = SKILLS_DIR / name / "SKILL.md"
        if not dir_form.is_file():
            errors.append(
                f"[{name}] flat '{flat.name}' has no dir form "
                f"'{name}/SKILL.md'. opencode only discovers the dir form — "
                f"copy flat -> {name}/SKILL.md."
            )
        elif _read(flat) != _read(dir_form):
            errors.append(
                f"[{name}] flat '{flat.name}' != dir '{name}/SKILL.md'. "
                f"They must be byte-identical (installer dual-writes both)."
            )

        source = SOURCE_DIR / flat.name
        if source.is_file():
            if _read(source) != _read(flat):
                errors.append(
                    f"[{name}] source 'skills_content/{flat.name}' != committed "
                    f"'.claude/skills/{flat.name}'. The source is canonical — a "
                    f"`devrel-agent install --force` would REVERT the committed "
                    f"copy. Back-port your edit into the source "
                    f"(cp .claude/skills/{flat.name} {source.relative_to(REPO)})."
                )
        elif name not in DEV_ONLY:
            errors.append(
                f"[{name}] committed but has NO skills_content source and is not "
                f"on DEV_ONLY. A `pip install` will NOT ship it. Either add "
                f"src/.../skills_content/{flat.name} or add '{name}' to DEV_ONLY "
                f"in {Path(__file__).name}."
            )

    if SOURCE_DIR.is_dir():
        for src in sorted(SOURCE_DIR.glob("*.md")):
            if src.stem not in flat_names:
                errors.append(
                    f"[{src.stem}] source 'skills_content/{src.name}' has no "
                    f"committed '.claude/skills/{src.name}'. Run "
                    f"`devrel-agent install --client claude_code --force` to "
                    f"materialize it, then commit."
                )

    if errors:
        print("Skill sync check FAILED:\n")
        for e in errors:
            print(f"  - {e}")
        print(f"\n{len(errors)} problem(s). See {Path(__file__).name} for the rules.")
        return 1

    n = len(flat_names)
    print(f"Skill sync check passed: {n} skill(s), all forms byte-identical.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
