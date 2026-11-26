---
name: npu-quantization-and-accuracy-gating
description: "Decide whether an int8 or mixed-precision version of the music model is accurate enough to use by comparing it with a reference using cosine similarity and rejecting versions that fall below threshold."
version: 0.1.0
---

# NPU Quantization and Accuracy Gating

Back to the [GesturDJ README](../../README.md).

The supported ACE-Step flow validates each of six NPU batches against the
qualified cosine gate. Follow the workflow and recorded results in
[`ACE-Step/IQ8_NPU_WAV_STATUS.md`](../../ACE-Step/IQ8_NPU_WAV_STATUS.md).

| Cosine against the reference | Verdict |
| --- | --- |
| 0.999 or more | qualified: generate |
| below 0.999 | unqualified: stop and investigate |

## Measured (Qualcomm IQ8, ACE-Step)

| Batch group | Final cosine | Verdict |
| --- | --- | --- |
| Blocks 0-3 | 0.9999539421 | qualified |
| Blocks 4-7 | 0.9998565466 | qualified |
| Blocks 8-11 | 0.9998298288 | qualified |
| Blocks 12-15 | 0.9997063599 | qualified |
| Blocks 16-19 | 0.9997924376 | qualified |
| Blocks 20-23 | 0.9999190429 | qualified |

The static ACE-Step contexts are qualified only for the documented tensor
shapes and instrumental condition. Changing quantization, contexts, or tensor
shapes requires requalification before generation.

Evidence: [`ACE-Step/IQ8_NPU_WAV_STATUS.md`](../../ACE-Step/IQ8_NPU_WAV_STATUS.md).

## Rules

- The threshold does not move to pass.
- A tensor-size mismatch means the request is outside the qualified static contract.
- Re-exported contexts require a full six-batch cosine qualification.

Complete when every ACE-Step batch meets the cosine gate, or a failed batch is
named.

<!-- skills-hub:begin -->

## Compatibility

| Item | Details |
| --- | --- |
| Devkits | Dragonwing IQ-8275 EVK (`qcs8275-iq-8275-evk-pro`) |
| Target OS | Qualcomm Linux (`qli-2.0`, `qualcomm-linux-proprietary`) |
| Host OS | Any |
| Requirements | Python 3.10+; PC and Qualcomm IQ8 board (Qualcomm Linux 2.0); QAIRT for the NPU music path |

References: [GesturDJ README](https://github.com/sreddygu/DevRel/blob/main/GesturDJ/README.md), [IQ8 SSH runbook](https://github.com/sreddygu/DevRel/blob/main/GesturDJ/ACE-Step/IQ8_SSH_RUNBOOK.md).

## Example prompts

- Is my int8 music model accurate enough compared to fp16?
- Compare mixed-precision and all-int8 outputs against the reference
- Which layers should stay in fp16 to keep accuracy?
- Accept or reject this quantized model using a 0.999 cosine threshold
- Run the accuracy gate on every batch of my quantized model
- Why did my quantized model fail the cosine check on batch 3?

<!-- skills-hub:end -->
