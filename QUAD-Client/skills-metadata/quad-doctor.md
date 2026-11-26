---
name: quad-doctor
description: "Run the local diagnostic suite for a QUAD (Qualcomm Unified AI Developer) installation and explain each warning with the exact fix: Python environment, QAIRT SDK paths, MCP server connectivity and mock versus real mode."
---

# QUAD Install Diagnostics

Run the local diagnostic suite for a QUAD (Qualcomm Unified AI Developer) installation and explain each warning with the exact fix: Python environment, QAIRT SDK paths, MCP server connectivity and mock versus real mode.

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
- **References:** [QUAD Client README](../README.md)
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/quad-doctor/SKILL.md)

## Use Cases

- Is QUAD set up correctly?
- Diagnose my QUAD install
- Why isn't QUAD running in real mode?
- Check my QAIRT SDK setup for QUAD
- Explain every warning from the QUAD doctor and how to fix it
- My QUAD MCP server is unreachable. What should I check?
