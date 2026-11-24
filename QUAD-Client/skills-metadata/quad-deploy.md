---
name: quad-deploy
description: "Deploy a converted model to a target device (Android phone, Arduino board or Snapdragon target) with deploy.sh and run remote profiling."
---

# QUAD Model Deployment

Deploy a converted model to a target device (Android phone, Arduino board or Snapdragon target) with deploy.sh and run remote profiling.

## Catalog

- **Level:** Project skill for QUAD-Client
- **Owner:** `sreddygu`
- **Category:** `devtools`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `quad-client`, `edge-ai`, `quad`, `deploy`, `qualcomm-ai`, `mcp`, `npu`, `snapdragon-x-elite`, `qairt`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`, `linux`
- **Requirements:** Python 3.10+; a reachable QUAD MCP server; Qualcomm AI Runtime (QAIRT) SDK 2.47 and Snapdragon X Elite for NPU workflows
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/quad-deploy/SKILL.md)

## Use Cases

- Deploy my model to my Android phone
- Push this model to my Snapdragon target and profile it
- Deploy to my IQ-9075 board
- Run the deploy script and collect remote profiling results
