---
name: quad-codegen
description: "Pick the right platform, language and SDK combination for a model and generate compilable inference code."
---

# QUAD Inference Code Generator

Pick the right platform, language and SDK combination for a model and generate compilable inference code.

## Catalog

- **Level:** Project skill for QUAD-Client
- **Owner:** `sreddygu`
- **Category:** `devtools`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `quad-client`, `edge-ai`, `quad`, `codegen`, `qualcomm-ai`, `mcp`, `npu`, `snapdragon-x-elite`, `qairt`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`, `linux`
- **Requirements:** Python 3.10+; a reachable QUAD MCP server; Qualcomm AI Runtime (QAIRT) SDK 2.47 and Snapdragon X Elite for NPU workflows
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/quad-codegen/SKILL.md)

## Use Cases

- Generate inference code for my model
- Write a C++ app for this QNN model
- Give me Python boilerplate to run this model on the NPU
- Create an Android JNI binding for my model
