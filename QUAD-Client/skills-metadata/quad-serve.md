---
name: quad-serve
description: "Walk through `quad serve`: start a local inference server, call its endpoint and load-test it."
---

# QUAD Inference Server

Walk through `quad serve`: start a local inference server, call its endpoint and load-test it.

## Catalog

- **Level:** Project skill for QUAD-Client
- **Owner:** `sreddygu`
- **Category:** `devtools`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `quad-client`, `edge-ai`, `quad`, `serve`, `qualcomm-ai`, `mcp`, `npu`, `snapdragon-x-elite`, `qairt`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`, `linux`
- **Requirements:** Python 3.10+; a reachable QUAD MCP server; Qualcomm AI Runtime (QAIRT) SDK 2.47 and Snapdragon X Elite for NPU workflows
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/quad-serve/SKILL.md)

## Use Cases

- Start an inference server for my model
- Expose the model as an HTTP API
- Load test my local endpoint
- Prepare this model for production serving
