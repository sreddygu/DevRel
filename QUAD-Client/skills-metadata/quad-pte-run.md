---
name: quad-pte-run
description: "Run or profile an ExecuTorch .pte file on the host, or describe how to invoke the on-device runner."
---

# QUAD ExecuTorch .pte Runner

Run or profile an ExecuTorch .pte file on the host, or describe how to invoke the on-device runner.

## Catalog

- **Level:** Project skill for QUAD-Client
- **Owner:** `sreddygu`
- **Category:** `devtools`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `quad-client`, `edge-ai`, `quad`, `pte`, `run`, `qualcomm-ai`, `mcp`, `npu`, `snapdragon-x-elite`, `qairt`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`, `linux`
- **Requirements:** Python 3.10+; a reachable QUAD MCP server; Qualcomm AI Runtime (QAIRT) SDK 2.47 and Snapdragon X Elite for NPU workflows
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/quad-pte-run/SKILL.md)

## Use Cases

- Run my .pte on this machine
- Profile my ExecuTorch model
- Deploy a .pte to my device and run it
- Show the runner command for the board
