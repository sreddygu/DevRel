---
name: library-generation-and-quality-evaluation
description: "Generate music clips in the background from style prompts with an on-device music model, then check each clip and the whole set with objective measurements such as loop seams."
version: 0.1.0
---

# Library Generation and Quality Evaluation

Back to the [GesturDJ README](../../README.md).

Fills the live mixer's clip library in the background. Generation takes minutes, so it never
sits on the live path. Gate the setup first with
[`npu-quantization-and-accuracy-gating`](../npu-quantization-and-accuracy-gating/SKILL.md).

## Generate

Generate one instrumental clip per prompt with the qualified ACE-Step workflow in
[`ACE-Step/README.md`](../../ACE-Step/README.md). The static IQ8 contexts support
only the documented six-token instrumental condition and 10.031021-second output.

## Evaluate

Use the generated WAV checks in
[`ACE-Step/IQ8_NPU_WAV_STATUS.md`](../../ACE-Step/IQ8_NPU_WAV_STATUS.md), including
the WAV header and board-health validation after each long run.

| Check | Pass rule |
| --- | --- |
| Length | exactly 10.031021 s |
| Format | stereo, 48 kHz, 16-bit PCM |
| Board health | zero external-abort events |
| NPU gate | cosine at least 0.999 for every qualified batch |

## Rules

- These checks find runtime-contract failures. They do not find bad music: a person listens.
- A failed run is regenerated only after the failed gate is understood. The check is not removed.

## Measured (Qualcomm IQ8, ACE-Step)

| Run | Steps | Seed | Checks |
| --- | --- | --- | --- |
| Smoke validation | 4 | 20261120 | pass |
| Quality baseline | 27 | 20261120 | pass |

The qualified 27-step run completes in 552.8 seconds with zero external-abort
events. The full validation record is in
[`ACE-Step/IQ8_NPU_WAV_STATUS.md`](../../ACE-Step/IQ8_NPU_WAV_STATUS.md).

Complete when the generated WAV satisfies the qualified contract, or a failed
gate is named.
