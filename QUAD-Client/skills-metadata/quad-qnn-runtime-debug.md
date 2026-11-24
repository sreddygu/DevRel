---
name: quad-qnn-runtime-debug
description: "Diagnose Qualcomm AI (QNN/QAIRT) runtime failures on already-compiled models: backend initialisation, ABI or version mismatch, symbol resolution and input contract errors."
---

# QNN Runtime Failure Debugging

Diagnose Qualcomm AI (QNN/QAIRT) runtime failures on already-compiled models: backend initialisation, ABI or version mismatch, symbol resolution and input contract errors.

## Catalog

- **Level:** Project skill for QUAD-Client
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `quad-client`, `edge-ai`, `quad`, `qnn`, `runtime`, `debug`, `qualcomm-ai`, `mcp`, `npu`, `snapdragon-x-elite`, `qairt`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`, `linux`
- **Requirements:** Python 3.10+; a reachable QUAD MCP server; Qualcomm AI Runtime (QAIRT) SDK 2.47 and Snapdragon X Elite for NPU workflows
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/quad-qnn-runtime-debug/SKILL.md)

## Use Cases

- QNN backend won't initialize. What is wrong?
- Unable to find a valid interface provider
- My model fails to load with a symbol error on the NPU
- Check for an SDK version mismatch between my model and runtime
