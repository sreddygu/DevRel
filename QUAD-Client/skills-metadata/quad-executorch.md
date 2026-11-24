---
name: quad-executorch
description: "Drive the PyTorch to .pte to profile to runner flow with a QUAD MCP server, using the executorch_mobilenet sample as the reference."
---

# QUAD ExecuTorch Export and Run

Drive the PyTorch to .pte to profile to runner flow with a QUAD MCP server, using the executorch_mobilenet sample as the reference.

## Catalog

- **Level:** Project skill for QUAD-Client
- **Owner:** `sreddygu`
- **Category:** `general`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `quad-client`, `edge-ai`, `quad`, `executorch`, `qualcomm-ai`, `mcp`, `npu`, `snapdragon-x-elite`, `qairt`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`, `linux`
- **Requirements:** Python 3.10+; a reachable QUAD MCP server; Qualcomm AI Runtime (QAIRT) SDK 2.47 and Snapdragon X Elite for NPU workflows
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/quad-executorch/SKILL.md)

## Use Cases

- Export my PyTorch model to ExecuTorch
- Make a .pte file and run it on the NPU
- Profile my ExecuTorch model with QUAD
- Follow the executorch_mobilenet sample for my own model
