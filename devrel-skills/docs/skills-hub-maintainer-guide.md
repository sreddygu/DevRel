# Skills Hub — Maintainer Guide

A guide for publishing skills to the Qualcomm Developer MCP Server's built-in catalog. Once a
skill is registered, the Skills Hub surfaces it to users as a context-aware suggestion and
installs it on request — no client-side deployment required.

---

## The Problem This Solves

Teams across Qualcomm and the community each build skills for their own area — hardware,
connectivity, AI, tooling. Left unmanaged, that produces thousands of skills across many
repositories with no way to find the right one, know when it's outdated, or tell which version
fits a given device. And "the right version" is not universal: a developer on IMSDK 2.0 should
not receive a skill written for IMSDK 3.0, even if it is the latest — it may call APIs that
don't exist in their environment.

The Skills Hub provides a standard manifest, a searchable catalog, context-aware install
suggestions, and one-command install/update. Skills are fetched from each team's GitHub
repository, so fixes reach users on the next hourly refresh with no cross-team coordination.
Critically, results are filtered by the developer's **connected environment** — host OS, devkit,
target OS, and SDK versions — and a single skill may publish **multiple versions**, each
targeting a different environment. The hub offers each user the newest version compatible with
their setup: a developer on SDK v1 gets the skill's v1 while one on SDK v2 gets its v2.

---

## Concepts

- **Skill** — a directory of files (prompts, scripts, config) that extends an agent. Once
  installed it lands at `~/.claude/skills/<name>/` or `~/.codex/skills/<name>/`.
- **Version** — a skill publishes one or more versions, each with its own compatibility and
  download location. The server auto-selects the best fit for the connected environment.
- **Manifest (`skills.json`)** — declares skills and/or delegates to other repos and folders.
- **Catalog** — the aggregated, searchable set of all skills the server discovers from the
  configured root sources.

**Flow:** the server fetches `skills.json` from each root source → follows `sources` entries
recursively → builds the catalog → users install via `download_skill` → triggers surface
relevant skills after specific MCP tools complete.

---

## Repository Structure

A single repo can host skills for many teams. Any directory may hold a `skills.json` that
declares skills directly, delegates to sub-folders/repos via `sources`, or both. The server
follows `sources` recursively (up to 3 levels) to build the full catalog.

```text
qualcomm-skills-repo/
├── skills.json              # root: delegates to team folders via "sources"
└── teams/
    ├── connectivity/
    │   ├── skills.json       # declares the wifi-manager skill
    │   └── wifi-manager/
    │       └── SKILL.md      # required per skill
    └── hardware/
        ├── skills.json
        └── gpio-controller/
            └── SKILL.md
```

---

## The Manifest

`skills.json` sits at a repo or folder root. The server validates it on every fetch; a parse
error rejects that manifest and falls back to scanning `SKILL.md` files (which drops all rich
metadata — always ship a valid manifest).

```json
{ "manifestVersion": 1, "sources": [ ... ], "skills": [ ... ] }
```

### `sources` — Federation

Each entry delegates discovery to another repo or a sub-folder.

| Field | Type | Required | Notes |
|---|---|---|---|
| `type` | `"repo"` \| `"folder"` | **Yes** | How to locate the delegated `skills.json`. |
| `repo` | string | `repo`: **Yes** · `folder`: No | GitHub slug, e.g. `"qualcomm-developer/qualcomm-skills"`. For a `folder`, omit to resolve inside the declaring repo. |
| `ref`  | string | No | Git ref (branch, tag, SHA). Defaults to `"main"`. Ignored for same-repo folder sources. |
| `path` | string | `folder` only | Repo-relative folder path, e.g. `"teams/connectivity"`. No leading `/`, no `..`. |

The server skips already-visited sources (cycle guard) and ignores sources beyond 3 levels deep.

### Skill entry

A skill has **skill-level identity/metadata** plus a **`versions` array**. Skill-level fields are
shared defaults; each version may override the metadata and always specifies its own download
location and compatibility.

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | **Yes** | Lowercase kebab-case (`^[a-z0-9]+(?:-[a-z0-9]+)*$`). The install directory name; catalog-unique. |
| `owner` | string | **Yes** | GitHub username or org. |
| `description` | string | **Yes** | Default description, shown in search and the install prompt. |
| `versions` | `Version[]` | **Yes** | One or more versions (see below). |
| `displayName` | string | No | Human-readable label. Falls back to `name`. |
| `agents` | `("claude"\|"codex")[]` | No | Supported agents. Defaults to both. |
| `category` | string | No | `hardware`, `connectivity`, `ai`, `devtools`, or `general`. |
| `tags` | string[] | No | Search keywords (highest search weight). |
| `useCases` | string[] | No | Natural-language task descriptions (high search weight). |
| `license` | string | No | SPDX identifier, e.g. `"MIT"`. |
| `homepage` | string | No | URL to docs or repo. |
| `triggers` | `Trigger[]` | No | Context-aware suggestions (see [Triggers](#triggers)). |

### Version entry

| Field | Type | Required | Notes |
|---|---|---|---|
| `version` | string | **Yes** | Unique within the skill. **List versions oldest → newest.** |
| `compatibility` | object | No | Environment this version targets (see [Compatibility](#compatibility)). Omit an axis to mean "any". |
| `ref` | string | No | Git ref this version's files live on. Defaults to the source's ref — point older versions at a maintenance branch or tag. |
| `path` | string | No | Repo-relative directory for this version's files. |
| `docPath` | string | No | Path to this version's `SKILL.md`; returned by `get_skill_documentation`. |
| `files` | string[] | No | Download globs, e.g. `["skills/wifi-manager/**"]`. **Must cover `SKILL.md`.** |
| `minIdeVersion` | string | No | Minimum MCP Server version, e.g. `"2.3.0"`. |
| `description`, `displayName`, `tags`, `useCases` | — | No | Per-version overrides of the skill-level defaults. |

---

## Compatibility

Each version declares the environment it targets. All axes are optional; an omitted axis means
"any". The server matches a version only when every declared axis is satisfied.

```json
"compatibility": {
  "devkits": ["qcs9075-iq-9075-evk", "qcs6490-rb3gen2-core-kit"],
  "hostOs": ["linux", "windows", "macos"],
  "targetOs": [
    { "os": "qualcomm_linux", "variant": "qualcomm-linux-proprietary", "minVersion": "qli-1.8", "maxVersion": "qli-2.0" }
  ],
  "sdks": [
    { "id": "QIMPSDK CORE", "minVersion": "2.1.1" }
  ]
}
```

| Axis | Shape | Notes |
|---|---|---|
| `devkits` | string[] | Devkit ids; must match `DevkitData`. |
| `hostOs` | string[] | `"linux"`, `"windows"`, `"macos"`. |
| `targetOs` | `{ os, variant, minVersion?, maxVersion? }[]` | `os`/`variant` are `DevkitData` ids; bounds are `DevkitData` OS version strings. |
| `sdks` | `{ id, minVersion?, maxVersion? }[]` | `id` is a canonical SDK id (e.g. `"QIMPSDK CORE"`); bounds are SDK release versions. |

### Finding the right values

You don't need to read `DevkitData` by hand. Every valid devkit id, `os`/`variant` id, and SDK
id — with each version list ordered oldest → newest so you can copy them straight into
`minVersion`/`maxVersion` — is published in the
**Compatibility Reference.** Look up
your devkit, pick the os/variant and SDK your skill targets, and use the listed values verbatim.

**Version ranges compare by `DevkitData` order, not string order.** Platform version strings
come in incompatible dialects — SDK tags (`2.1.1`), Qualcomm Linux tags (`qli-2.0-rc3`), Ubuntu
tags (`24.04-x12`) — so string comparison is wrong (`"2.10" < "2.9"`). Instead the server
resolves each version to its position in the ordered list `DevkitData` publishes for that
devkit, and compares positions. Your `min`/`maxVersion` values must therefore be **real version
strings that exist in `DevkitData`** for the devkits you list. Unresolved references are logged
as warnings on refresh; filtering itself is **fail-open** (an unresolved version is shown, not
hidden — but fix the warning so the range takes effect).

**Matching rules.** `devkits`, `hostOs`, and `targetOs` must all be satisfied. Target OS is
matched on the connected device's OS id and version (the runtime OS *variant* is generally not
known, so `variant` is a manifest-side qualifier and is not itself matched against the device).
For `sdks`, a version is excluded only when the developer *has* a declared SDK and its version is
out of range — SDKs the developer lacks are ignored. Version-range checks need a known devkit;
without one, version axes fail open.

**Authoring guidance.** Declare only the axes that genuinely constrain the version, using the
tightest range you have actually tested. When a new SDK/OS generation ships, add a **new
version** with its own range rather than widening an existing one — that is what lets a user on
the old generation keep the old version.

---

## Versioning: one skill, many environments

The most important capability of the manifest is that a skill can serve different environments
from a single catalog entry. List each version oldest → newest; the server returns the **newest
version whose `compatibility` matches** the connected environment.

The example below ships a skill whose API changed between SDK generations. v1 stays on a
maintenance branch for devices on the SDK v1 / `qli-1.8` line; v2 lives on `main` for the SDK v2
/ `qli-2.0` line.

```json
{
  "name": "gpio-controller",
  "owner": "qualcomm-developer",
  "description": "Control GPIO pins on Qualcomm embedded boards.",
  "category": "hardware",
  "tags": ["gpio", "hardware", "embedded", "pins"],
  "versions": [
    {
      "version": "1.4.0",
      "ref": "release/1.x",
      "path": "skills/gpio-controller",
      "files": ["skills/gpio-controller/**"],
      "description": "GPIO control using the SDK v1 / QIMPSDK CORE 2.x API.",
      "compatibility": {
        "targetOs": [{ "os": "qualcomm_linux", "variant": "qualcomm-linux-proprietary", "minVersion": "qli-1.8", "maxVersion": "qli-1.8" }],
        "sdks": [{ "id": "QIMPSDK CORE", "minVersion": "2.0.1", "maxVersion": "2.2.1" }]
      }
    },
    {
      "version": "2.0.0",
      "path": "skills/gpio-controller",
      "files": ["skills/gpio-controller/**"],
      "description": "GPIO control using the SDK v2 / QIMPSDK CORE 3.x API.",
      "compatibility": {
        "targetOs": [{ "os": "qualcomm_linux", "variant": "qualcomm-linux-proprietary", "minVersion": "qli-2.0" }],
        "sdks": [{ "id": "QIMPSDK CORE", "minVersion": "3.0.0" }]
      }
    }
  ]
}
```

- A device on QIMPSDK CORE 2.1 is offered **v1.4.0**; a device on CORE 3.0 is offered **v2.0.0**.
- If no version matches, the skill does not appear at all.
- `download_skill` and `get_skill_documentation` act on the same best-matching version by
  default; pass an explicit `version` to override.
- Each version downloads from its own `ref`/`path`, so v1 can remain on `release/1.x` while
  `main` carries v2.

### Other common shapes

**Single-version skill** — the common case; one entry in `versions`:

```json
{
  "name": "wifi-manager",
  "owner": "qualcomm-developer",
  "description": "Manage Wi-Fi connections via wpa_supplicant or NetworkManager.",
  "category": "connectivity",
  "versions": [
    {
      "version": "1.2.0",
      "path": "skills/wifi-manager",
      "files": ["skills/wifi-manager/**"],
      "compatibility": {
        "sdks": [{ "id": "QIMPSDK CORE", "minVersion": "2.2.1" }]
      }
    }
  ]
}
```

**SDK-agnostic, host-restricted skill** — omit `sdks` entirely; constrain only what matters:

```json
{
  "name": "uart-bridge",
  "owner": "qualcomm-developer",
  "description": "Communicate over UART serial ports.",
  "category": "hardware",
  "versions": [
    {
      "version": "0.9.1",
      "path": "skills/uart-bridge",
      "files": ["skills/uart-bridge/**"],
      "minIdeVersion": "1.5.0",
      "compatibility": { "hostOs": ["linux", "windows"] }
    }
  ]
}
```

**Fully portable skill** — omit `compatibility` (or leave it empty) so the skill matches every
environment.

The complete, runnable sample is at
[`skills-hub-sample-manifest.json`](../skills-hub-sample-manifest.json).

---

## Triggers

A trigger fires **after** a named MCP tool completes — "now that this tool finished, what does
the user want next, and is there a skill for it?"

```json
{ "action": "suggest-install" | "suggest-uninstall", "tool": "<mcp-tool-name>" }
```

- **`suggest-install`** fires when the tool completes and the skill is **not installed** — use it
  when your skill is the logical next step.
- **`suggest-uninstall`** fires when the skill **is installed** — use it when the tool's success
  means the skill is no longer needed.

| After this tool… | Action | Skill | Rationale |
|---|---|---|---|
| `list_devices` | suggest-install | `gpio-controller` | Board connected; user will want to control pins. |
| `provision_network` | suggest-install | `wifi-manager` | Device on the network; manage the connection. |
| `finalize_provisioning` | suggest-uninstall | `device-setup-wizard` | Provisioning done; setup skill is redundant. |

> Don't trigger on loosely related tools — a tip in the wrong context trains users to ignore all
> tips.

---

## The `SKILL.md` File

Every skill directory must contain `SKILL.md`. It is both the **installation gate** (the server
refuses to install files that don't include it) and the **documentation** returned by
`get_skill_documentation`. Include YAML front matter (used by the fallback scanner when no
manifest is present):

```markdown
---
name: wifi-manager
description: Manage Wi-Fi connections using wpa_supplicant or NetworkManager.
version: 1.2.0
---

# Wi-Fi Manager

What the skill does and when to use it.

## Usage
How the agent invokes it, including required arguments or env vars.

## Examples
- "Connect to my home Wi-Fi network"
- "Show visible access points and their signal strength"

## Requirements
System packages, firmware versions, or permissions needed.
```

---

## How Discovery, Selection & Install Work

**Discovery.** On each refresh (hourly, or on-demand via `refresh_skills_catalog`) the server
fetches `skills.json` from every configured root, following `sources` recursively up to 3 levels,
skipping visited sources. Conditional fetches (`If-None-Match`) avoid redundant downloads. The root
sources are configured in the MCP Server itself.

**Environment resolution.** Compatibility is filtered against the connected setup automatically —
the agent supplies nothing. The server reads:

- **Devkit** — from the selected device.
- **Target OS (id + version)** — from the connected device. The OS *variant* is not read from the
  device, so target-OS matching uses OS id + version.
- **Installed SDKs** — id + version per SDK installed for the active devkit.
- **Host OS** — the machine running the MCP server.

An agent may override any axis on `search_skills` (e.g. "what could I run if I flashed a newer
OS?"); overrides win per axis, and unset axes simply don't filter.

**Selection.** For each skill, the server picks the newest version whose `compatibility` matches,
then ranks results by search relevance.

**Install.** `download_skill` selects the version (best match, or explicit `version`), then:

1. Resolves `files` globs via the GitHub Trees API at that version's `ref`.
2. Requires a `SKILL.md` under the version's root, or refuses.
3. Downloads to a staging directory with a `.skills-hub.json` marker whose `key` encodes repo +
   ref + root + version.
4. Atomically moves staging to `<skills-dir>/<name>/`, replacing a prior Skills Hub install.
   Unmanaged directories (no marker) are never overwritten.

Re-installing the same version is a no-op. Don't include `.skills-hub.json` in your `files` — the
server writes it.

---

## Publishing Checklist

- [ ] `skills.json` at the repo/folder root with `manifestVersion: 1`.
- [ ] Each skill has `name` (kebab-case), `owner`, `description`, and ≥1 `versions` entry.
- [ ] Versions have unique `version` strings, listed oldest → newest.
- [ ] Each version's `files` glob covers its `SKILL.md` at that version's `ref`/`path`.
- [ ] Each `docPath` points to an existing `SKILL.md`; `SKILL.md` has front matter.
- [ ] Trigger `tool` values are real MCP tool names.
- [ ] Each version's `compatibility` uses ids/versions from the [Compatibility
      reference — check refresh logs
      for warnings if a value doesn't resolve.
- [ ] `sources` use valid `owner/repo` slugs; the repository is publicly readable.

To request catalog inclusion, contact the Skills Hub team with your `owner/repo`, the git ref to
track, the source type (`repo` or `folder`), and a short description. They add your entry to the
registry's root `skills.json`.
