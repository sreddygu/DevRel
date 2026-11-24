---
name: quad-detect
description: "Probe the local machine and any reachable devices (USB boards via adb, SSH targets in quad.toml) and report chipset, CPU/GPU/NPU, RAM, runtimes and SDK status."
---

# QUAD Hardware Detection

Probe the local machine and any reachable devices (USB boards via adb, SSH targets in quad.toml) and report chipset, CPU/GPU/NPU, RAM, runtimes and SDK status.

## Catalog

- **Level:** Project skill for QUAD-Client
- **Owner:** `sreddygu`
- **Category:** `general`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `quad-client`, `edge-ai`, `quad`, `detect`, `qualcomm-ai`, `mcp`, `npu`, `snapdragon-x-elite`, `qairt`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`, `linux`
- **Requirements:** Python 3.10+; a reachable QUAD MCP server; Qualcomm AI Runtime (QAIRT) SDK 2.47 and Snapdragon X Elite for NPU workflows
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/quad-detect/SKILL.md)

## Use Cases

- What hardware do I have?
- Do I have an NPU on this machine?
- Probe my IQ-9075 board over SSH
- What targets are connected right now?
