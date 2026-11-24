---
name: quad-build-npu-bundle
description: "Build an AI Hub Genie bundle for a large language model on a non-ARM64 host (WSL, x86, macOS or Linux) and copy it to a Snapdragon X Elite PC where it runs on the Hexagon NPU."
---

# NPU LLM Bundle Builder

Build an AI Hub Genie bundle for a large language model on a non-ARM64 host (WSL, x86, macOS or Linux) and copy it to a Snapdragon X Elite PC where it runs on the Hexagon NPU.

## Catalog

- **Level:** Project skill for QUAD-Client
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `quad-client`, `edge-ai`, `quad`, `build`, `npu`, `bundle`, `qualcomm-ai`, `mcp`, `snapdragon-x-elite`, `qairt`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `linux`, `windows`, `macos`
- **Requirements:** Python 3.10+; a reachable QUAD MCP server; Qualcomm AI Runtime (QAIRT) SDK 2.47 and Snapdragon X Elite for NPU workflows
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/quad-build-npu-bundle/SKILL.md)

## Use Cases

- Build an NPU bundle for Llama on my x86 machine
- Export a Qwen model for the Hexagon NPU
- Download a model for the NPU provider and stage it on my Snapdragon PC
- Prepare a Genie bundle in WSL
