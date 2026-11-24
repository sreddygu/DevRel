---
name: edge-agent-runtime-setup
description: "Prepare and inspect the EdgeAgent runtime (llama.cpp CPU backend or Genie NPU backend) on a Snapdragon X Elite PC or IQ8/IQ9 board without changing MCP client settings by default."
---

# EdgeAgent Runtime Setup

Prepare and inspect the EdgeAgent runtime (llama.cpp CPU backend or Genie NPU backend) on a Snapdragon X Elite PC or IQ8/IQ9 board without changing MCP client settings by default.

## Catalog

- **Level:** Project skill for EdgeAgent
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `edgeagent`, `edge-ai`, `edge`, `agent`, `runtime`, `setup`, `edge-agent`, `ai-agent`, `llm`, `snapdragon-x-elite`, `iq8`, `iq9`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`, `qcs9075-iq-9075-evk`; target OS `qualcomm_linux` (qli-2.0); host OS `windows`, `linux`
- **Requirements:** Python 3.10+; llama.cpp server (CPU) or Genie shim over QAIRT (NPU, Snapdragon X Elite host)
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/edge-agent-runtime-setup/SKILL.md)

## Use Cases

- Set up EdgeAgent with a local llama.cpp server
- Point EdgeAgent at the Genie NPU backend on my Snapdragon X Elite PC
- Check whether EdgeAgent can reach its model server on my IQ8
- What do I need installed to run EdgeAgent on an IQ9 board?
