---
name: quad-profile
description: "Pick the right profiling level and show a summary of latency and utilisation, including bottlenecks and QHAS profiling."
---

# QUAD Model Profiler

Pick the right profiling level and show a summary of latency and utilisation, including bottlenecks and QHAS profiling.

## Catalog

- **Level:** Project skill for QUAD-Client
- **Owner:** `sreddygu`
- **Category:** `devtools`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `quad-client`, `edge-ai`, `quad`, `profile`, `qualcomm-ai`, `mcp`, `npu`, `snapdragon-x-elite`, `qairt`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`, `linux`
- **Requirements:** Python 3.10+; a reachable QUAD MCP server; Qualcomm AI Runtime (QAIRT) SDK 2.47 and Snapdragon X Elite for NPU workflows
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/quad-profile/SKILL.md)

## Use Cases

- Profile my model and find bottlenecks
- Measure NPU latency for this model
- Run QHAS profiling
- Lint my model for NPU-unfriendly ops
