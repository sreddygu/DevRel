---
name: quad-app-builder
description: "Guide the full lifecycle of a Snapdragon AI application built with QUAD (Qualcomm Unified AI Developer): requirements, implementation, testing, hardening, documentation and git push, for example a vision, speech or LLM app on the NPU."
---

# Snapdragon AI Application Builder

Guide the full lifecycle of a Snapdragon AI application built with QUAD (Qualcomm Unified AI Developer): requirements, implementation, testing, hardening, documentation and git push, for example a vision, speech or LLM app on the NPU.

## Catalog

- **Level:** Project skill for QUAD-Client
- **Owner:** `sreddygu`
- **Category:** `devtools`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `quad-client`, `edge-ai`, `quad`, `app`, `builder`, `qualcomm-ai`, `mcp`, `npu`, `snapdragon-x-elite`, `qairt`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`, `linux`
- **Requirements:** Python 3.10+; a reachable QUAD MCP server; Qualcomm AI Runtime (QAIRT) SDK 2.47 and Snapdragon X Elite for NPU workflows
- **References:** [QUAD Client README](../README.md)
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/quad-app-builder/SKILL.md)

## Use Cases

- Build a vision app on Snapdragon with QUAD
- Create a QUAD application that runs an LLM on the NPU
- Scaffold an inference app and test it end to end
- I want to build a speech-recognition app on my Snapdragon X Elite laptop
- Add tests and documentation to my Snapdragon app and push it to git
- Harden my app: error handling, input validation and logging
