---
name: quad-doctor
description: "Run the local diagnostic suite for a QUAD install and explain each warning with the exact fix."
---

# QUAD Install Diagnostics

Run the local diagnostic suite for a QUAD install and explain each warning with the exact fix.

## Catalog

- **Level:** Project skill for QUAD-Client
- **Owner:** `sreddygu`
- **Category:** `devtools`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `quad-client`, `edge-ai`, `quad`, `doctor`, `qualcomm-ai`, `mcp`, `npu`, `snapdragon-x-elite`, `qairt`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`, `linux`
- **Requirements:** Python 3.10+; a reachable QUAD MCP server; Qualcomm AI Runtime (QAIRT) SDK 2.47 and Snapdragon X Elite for NPU workflows
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/quad-doctor/SKILL.md)

## Use Cases

- Is QUAD set up correctly?
- Diagnose my QUAD install
- Why isn't real mode working?
- Check my SDK setup for QUAD
