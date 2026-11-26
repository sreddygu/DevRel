---
name: quad-npu-prereqs
description: "Detect the host architecture and target, review the Qualcomm AI Hub token, NPU Python wheels and environment prerequisites with you, then provision whatever is missing for Hexagon NPU development with QUAD (Qualcomm Unified AI Developer)."
---

# Snapdragon NPU Development Prerequisites

Detect the host architecture and target, review the Qualcomm AI Hub token, NPU Python wheels and environment prerequisites with you, then provision whatever is missing for Hexagon NPU development with QUAD (Qualcomm Unified AI Developer).

## Catalog

- **Level:** Project skill for QUAD-Client
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `quad-client`, `edge-ai`, `quad`, `npu`, `prereqs`, `qualcomm-ai`, `mcp`, `snapdragon-x-elite`, `qairt`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`, `linux`
- **Requirements:** Python 3.10+; a reachable QUAD MCP server; Qualcomm AI Runtime (QAIRT) SDK 2.47 and Snapdragon X Elite for NPU workflows
- **References:** [QUAD Client README](../README.md)
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/quad-npu-prereqs/SKILL.md)

## Use Cases

- Set up my machine to develop for the Hexagon NPU
- What prerequisites do I need to run a model on the NPU?
- Configure my AI Hub token and NPU wheels
- Prepare my Snapdragon laptop for NPU builds
- Why can't my Python environment find the NPU backend?
- Check my ARM64 Python and QAIRT versions match
