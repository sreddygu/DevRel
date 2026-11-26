---
name: quad-recommend
description: "Combine your model, target device and use case into specific deployment recommendations with QUAD (Qualcomm Unified AI Developer), such as NPU or GPU and INT4 or INT8 precision."
---

# NPU vs GPU Deployment Recommendations

Combine your model, target device and use case into specific deployment recommendations with QUAD (Qualcomm Unified AI Developer), such as NPU or GPU and INT4 or INT8 precision.

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
- **References:** [QUAD Client README](../README.md)
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/quad-recommend/SKILL.md)

## Use Cases

- What's the best way to deploy this model on Snapdragon?
- Should I use INT4 or INT8?
- NPU or GPU for my LLM?
- Recommend an approach for a real-time vision model on a Snapdragon X Elite laptop
- Which precision gives the best speed for my speech-recognition model?
- What are the trade-offs of running my model on the NPU instead of the CPU?
