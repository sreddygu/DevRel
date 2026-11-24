---
name: npu-quantization-and-accuracy-gating
description: "Decide whether an int8 or mixed-precision version of the music model is accurate enough to use by comparing it with a reference using cosine similarity and rejecting versions that fall below threshold."
---

# NPU Quantization Accuracy Gate

Decide whether an int8 or mixed-precision version of the music model is accurate enough to use by comparing it with a reference using cosine similarity and rejecting versions that fall below threshold.

## Catalog

- **Level:** Project skill for GesturDJ
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `gesturdj`, `edge-ai`, `npu`, `quantization`, `accuracy`, `gating`, `gesture-recognition`, `music`, `iq8`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`; target OS `qualcomm_linux` (qli-2.0)
- **Requirements:** Python 3.10+; PC and Qualcomm IQ8 board (Qualcomm Linux 2.0); QAIRT for the NPU music path
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/npu-quantization-and-accuracy-gating/SKILL.md)

## Use Cases

- Is my int8 music model accurate enough compared to fp16?
- Compare mixed-precision and all-int8 outputs against the reference
- Which layers should stay in fp16 to keep accuracy?
- Accept or reject this quantized model with a cosine threshold
