---
name: quad-client-installation
description: "Install and validate the QUAD client (quad-mcp-client) and choose how it reaches the QUAD server (hosted URL, SSH or local), without changing MCP settings by default."
---

# QUAD Client Installation

Install and validate the QUAD client (quad-mcp-client) and choose how it reaches the QUAD server (hosted URL, SSH or local), without changing MCP settings by default.

## Catalog

- **Level:** Project skill for QUAD-Client
- **Owner:** `sreddygu`
- **Category:** `devtools`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `quad-client`, `edge-ai`, `quad`, `client`, `installation`, `qualcomm-ai`, `mcp`, `npu`, `snapdragon-x-elite`, `qairt`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`, `linux`
- **Requirements:** Python 3.10+; a reachable QUAD MCP server; Qualcomm AI Runtime (QAIRT) SDK 2.47 and Snapdragon X Elite for NPU workflows
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/quad-client-installation/SKILL.md)

## Use Cases

- Install the QUAD client and connect it to my QUAD server
- Which transport should I choose: hosted, SSH or local?
- Validate my QUAD client installation
- Why can't Claude Code reach my QUAD server?
