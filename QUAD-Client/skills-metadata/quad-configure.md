---
name: quad-configure
description: "Interactive wizard that asks about SDK paths, hardware and secrets, then writes quad.toml and .env. Run before first use or when hardware or SDK setup changes."
---

# QUAD Configuration Wizard

Interactive wizard that asks about SDK paths, hardware and secrets, then writes quad.toml and .env. Run before first use or when hardware or SDK setup changes.

## Catalog

- **Level:** Project skill for QUAD-Client
- **Owner:** `sreddygu`
- **Category:** `devtools`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `quad-client`, `edge-ai`, `quad`, `configure`, `qualcomm-ai`, `mcp`, `npu`, `snapdragon-x-elite`, `qairt`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`, `linux`
- **Requirements:** Python 3.10+; a reachable QUAD MCP server; Qualcomm AI Runtime (QAIRT) SDK 2.47 and Snapdragon X Elite for NPU workflows
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/quad-configure/SKILL.md)

## Use Cases

- Configure QUAD for the first time
- Set my QAIRT SDK path and target hardware for QUAD
- Generate quad.toml and .env for my project
- I changed my SDK location. Update the QUAD configuration
