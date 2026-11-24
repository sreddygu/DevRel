---
name: device-agent-evaluation
description: "Run an approved evaluation of the EdgeAgent tool-using LLM agent on a Snapdragon X Elite PC or IQ8/IQ9 board and record target-specific results."
---

# EdgeAgent On-Device Evaluation

Run an approved evaluation of the EdgeAgent tool-using LLM agent on a Snapdragon X Elite PC or IQ8/IQ9 board and record target-specific results.

## Catalog

- **Level:** Project skill for EdgeAgent
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `edgeagent`, `edge-ai`, `device`, `agent`, `evaluation`, `edge-agent`, `ai-agent`, `llm`, `snapdragon-x-elite`, `iq8`, `iq9`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`, `qcs9075-iq-9075-evk`; target OS `qualcomm_linux` (qli-2.0); host OS `windows`, `linux`
- **Requirements:** Python 3.10+; llama.cpp server (CPU) or Genie shim over QAIRT (NPU, Snapdragon X Elite host)
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/device-agent-evaluation/SKILL.md)

## Use Cases

- Evaluate EdgeAgent with the local model on my IQ9 board
- Compare EdgeAgent tool-use accuracy on CPU and NPU
- Record latency and tool-call results for EdgeAgent on this device
- Run the EdgeAgent evaluation and save the evidence
