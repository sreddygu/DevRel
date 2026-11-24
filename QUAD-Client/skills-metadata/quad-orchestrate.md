---
name: quad-orchestrate
description: "Compare performance, balanced and efficiency modes side by side and recommend where each operation should run across CPU, GPU and NPU."
---

# QUAD CPU/GPU/NPU Allocation Advisor

Compare performance, balanced and efficiency modes side by side and recommend where each operation should run across CPU, GPU and NPU.

## Catalog

- **Level:** Project skill for QUAD-Client
- **Owner:** `sreddygu`
- **Category:** `general`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `quad-client`, `edge-ai`, `quad`, `orchestrate`, `qualcomm-ai`, `mcp`, `npu`, `snapdragon-x-elite`, `qairt`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`, `linux`
- **Requirements:** Python 3.10+; a reachable QUAD MCP server; Qualcomm AI Runtime (QAIRT) SDK 2.47 and Snapdragon X Elite for NPU workflows
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/quad-orchestrate/SKILL.md)

## Use Cases

- Allocate this model across CPU, GPU and NPU
- Compare power modes for my workload
- Where should this op run?
- Which mode gives the best latency per watt?
