# Skill files — source of truth & sync policy

This repo ships Claude Code / opencode **skills**. Each skill can exist in up
to three on-disk forms, and they must not drift. This document is the policy;
`scripts/check_skills_sync.py` enforces it in CI.

## The three forms

| Form | Path | Role |
|---|---|---|
| **source** | `src/devrel_client/claude_code/skills_content/<name>.md` | **Canonical.** Bundled into the wheel so `pip install` ships it. |
| **flat** | `.claude/skills/<name>.md` | What older Claude Code / some CLIs read. |
| **dir** | `.claude/skills/<name>/SKILL.md` | What modern Claude Code **and opencode** read. opencode discovers *only* this form. |

The installer (`devrel-agent install --client claude_code --force`) is a **pure
`shutil.copy2`** from source → flat + dir. No frontmatter rewriting. Therefore,
**when a skill is in sync, all present forms are byte-identical.**

## Rules (enforced by `scripts/check_skills_sync.py`)

1. `flat` and `dir` must both exist and be **byte-identical**.
2. If a `source` exists, it must equal `flat` (and thus `dir`). **The source is
   canonical** — a `--force` install would overwrite flat/dir from it, so an
   edit that lives only in flat/dir will be silently reverted.
3. A committed-only skill (no source) is allowed **only** if it is on the
   `DEV_ONLY` allowlist in the check script. Otherwise it must have a source, or
   `pip install` users never get it.
4. No orphan sources (a source with no committed flat/dir).

## How to edit a skill (the only correct workflow)

```bash
# 1. Edit the SOURCE (canonical):
$EDITOR src/devrel_client/claude_code/skills_content/<name>.md

# 2. Regenerate flat + dir from it:
devrel-agent install --client claude_code --force
#    (or, by hand: cp <name>.md .claude/skills/<name>.md
#                   cp <name>.md .claude/skills/<name>/SKILL.md)

# 3. Verify + commit all three:
python scripts/check_skills_sync.py
git add src/.../skills_content/<name>.md .claude/skills/<name>.md .claude/skills/<name>/SKILL.md
```

Never hand-edit `.claude/skills/<name>.md` alone — CI will fail, and the next
`--force` install would discard your change.

## DEV_ONLY (committed-only, not shipped via pip)

Empty today — the client ships every user-facing skill via `skills_content/`.
Add a name to the `DEV_ONLY` set in the check script only for a genuine
developer-only skill that should not reach end users.

## Cross-repo divergence is allowed and intentional

The same skill name may exist in both `DevRel` (the server) and `devrelAgent`
(the thin client) with **different content** — by design, because the audiences
differ. Examples today: `devrel-doctor`, `devrel-quickstart`, `devrel-codegen` (the
client versions are scoped to `devrel-agent` tooling / local diagnostics).

The sync guard runs **per repo** and only enforces source==flat==dir *within*
that repo. It does **not** force the two repos to match. When you change a skill
that lives in both repos and the change is relevant to both audiences, update
both copies deliberately; otherwise leave the other repo's version alone.
