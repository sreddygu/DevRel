---
name: edge-agent-runtime-setup
description: "Set up and inspect EdgeAgent, a portable tool-using LLM agent, with a llama.cpp CPU backend or a Qualcomm AI Runtime (QAIRT) Genie NPU backend, on a Snapdragon X Elite PC or a Qualcomm Dragonwing IQ-8275 (IQ8) or Dragonwing IQ-9075 (IQ9) board, and preview its MCP client configuration before anything is written."
---

# EdgeAgent Local LLM Agent Setup

Set up and inspect EdgeAgent, a portable tool-using LLM agent, with a llama.cpp CPU backend or a Qualcomm AI Runtime (QAIRT) Genie NPU backend, on a Snapdragon X Elite PC or a Qualcomm Dragonwing IQ-8275 (IQ8) or Dragonwing IQ-9075 (IQ9) board, and preview its MCP client configuration before anything is written.

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
- **References:** [EdgeAgent README](../README.md), [Run on IQ8](../RUN_ON_IQ8.md), [NPU quickstart](../devrel_runtime/docs/NPU_QUICKSTART.md)
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/edge-agent-runtime-setup/SKILL.md)

## Use Cases

- Set up EdgeAgent with a local llama.cpp server
- Point EdgeAgent at the Genie NPU backend on my Snapdragon X Elite PC
- Run the EdgeAgent doctor check and explain every failure
- Preview the MCP client configuration for the stdio-ssh transport without installing it
- Check whether EdgeAgent can reach its model server on my IQ8
- What do I need installed to run EdgeAgent on an IQ9 board?
- Which EdgeAgent transport fits my setup: stdio-local, stdio-ssh or sse-http?
