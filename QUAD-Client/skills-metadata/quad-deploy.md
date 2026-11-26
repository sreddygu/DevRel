---
name: quad-deploy
description: "Deploy a converted model with QUAD (Qualcomm Unified AI Developer) to a target device (an Android phone, an Arduino board or a Snapdragon device such as the Dragonwing IQ-9075) using deploy.sh, and collect remote profiling results."
---

# Model Deployment to a Snapdragon Target

Deploy a converted model with QUAD (Qualcomm Unified AI Developer) to a target device (an Android phone, an Arduino board or a Snapdragon device such as the Dragonwing IQ-9075) using deploy.sh, and collect remote profiling results.

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
- **References:** [QUAD Client README](../README.md)
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/quad-deploy/SKILL.md)

## Use Cases

- Deploy my model to my Android phone
- Push this model to my Snapdragon target and profile it
- Deploy to my Dragonwing IQ-9075 board
- Run the deploy script and collect remote profiling results
- My deployed model fails to start on the device. What do I check?
- Deploy my model to my Arduino board
