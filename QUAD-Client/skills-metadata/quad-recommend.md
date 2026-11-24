---
name: quad-recommend
description: "Combine model, target and use case into specific deployment recommendations, such as NPU or GPU and INT4 or INT8."
---

# QUAD Deployment Recommendations

Combine model, target and use case into specific deployment recommendations, such as NPU or GPU and INT4 or INT8.

## Catalog

- **Level:** Project skill for QUAD-Client
- **Owner:** `sreddygu`
- **Category:** `general`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `quad-client`, `edge-ai`, `quad`, `recommend`, `qualcomm-ai`, `mcp`, `npu`, `snapdragon-x-elite`, `qairt`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`, `linux`
- **Requirements:** Python 3.10+; a reachable QUAD MCP server; Qualcomm AI Runtime (QAIRT) SDK 2.47 and Snapdragon X Elite for NPU workflows
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/quad-recommend/SKILL.md)

## Use Cases

- What's the best way to deploy this model on Snapdragon?
- Should I use INT4 or INT8?
- NPU or GPU for my LLM?
- Recommend an approach for a real-time vision model
