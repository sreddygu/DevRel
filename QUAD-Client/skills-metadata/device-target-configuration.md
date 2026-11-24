---
name: device-target-configuration
description: "Discover and document an approved device target for the QUAD client (IQ-9075 board over SSH, Android over adb) without changing the device by default."
---

# QUAD Device Target Setup

Discover and document an approved device target for the QUAD client (IQ-9075 board over SSH, Android over adb) without changing the device by default.

## Catalog

- **Level:** Project skill for QUAD-Client
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `quad-client`, `edge-ai`, `device`, `target`, `configuration`, `qualcomm-ai`, `mcp`, `npu`, `snapdragon-x-elite`, `qairt`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs9075-iq-9075-evk`; target OS `qualcomm_linux` (qli-2.0)
- **Requirements:** Python 3.10+; a reachable QUAD MCP server; Qualcomm AI Runtime (QAIRT) SDK 2.47 and Snapdragon X Elite for NPU workflows
- **Hub triggers:** `suggest-install` after `get_active_device`
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/device-target-configuration/SKILL.md)

## Use Cases

- Add my IQ-9075 board as a QUAD target over SSH
- Document the device target QUAD will deploy to
- Check the target configuration before I deploy a model
- Which QUAD transport should I use for my board?
