---
name: agent-tool-contract-validation
description: "Validate the MCP client configuration that EdgeAgent (a small tool-using LLM agent for local and edge devices) generates for a chosen transport, and confirm a failed connection is reported, before anything is installed."
---

# EdgeAgent MCP Connection Check

Validate the MCP client configuration that EdgeAgent (a small tool-using LLM agent for local and edge devices) generates for a chosen transport, and confirm a failed connection is reported, before anything is installed.

## Catalog

- **Level:** Project skill for EdgeAgent
- **Owner:** `sreddygu`
- **Category:** `devtools`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `edgeagent`, `edge-ai`, `agent`, `tool`, `contract`, `validation`, `edge-agent`, `ai-agent`, `llm`, `snapdragon-x-elite`, `iq8`, `iq9`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`, `qcs9075-iq-9075-evk`; target OS `qualcomm_linux` (qli-2.0); host OS `windows`, `linux`
- **Requirements:** Python 3.10+; llama.cpp server (CPU) or Genie shim over QAIRT (NPU, Snapdragon X Elite host)
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/agent-tool-contract-validation/SKILL.md)

## Use Cases

- Preview the MCP configuration EdgeAgent will write for my transport
- Test the connection to my EdgeAgent MCP server before I install it
- Why does my MCP client fail to connect to EdgeAgent?
- Run the EdgeAgent CLI connection tests
