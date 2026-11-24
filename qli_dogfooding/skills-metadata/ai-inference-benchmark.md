---
name: ai-inference-benchmark
description: "Benchmark a model command found on a Qualcomm Linux (QLI) device with explicit warm-up and iteration counts."
---

# Qualcomm Linux AI Inference Benchmark

Benchmark a model command found on a Qualcomm Linux (QLI) device with explicit warm-up and iteration counts.

## Catalog

- **Level:** Project skill for qli_dogfooding
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `2.0.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `edge-ai`, `inference`, `benchmark`, `qli-linux`, `qualcomm-linux`, `qli`, `iq8`, `iq9`, `readiness`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`, `qcs9075-iq-9075-evk`; target OS `qualcomm_linux` (qli-2.0)
- **Requirements:** Qualcomm Linux 2.0 on IQ8 or IQ9; SSH access; Python 3.10+ on the host
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/ai-inference-benchmark/SKILL.md)

## Use Cases

- Benchmark the sample model on my IQ9 board
- Measure inference latency with 10 warm-up runs and 100 iterations
- How fast does this model run on my device?
- Compare benchmark results before and after changing the model
