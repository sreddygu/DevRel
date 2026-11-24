---
name: npu-quantization-and-accuracy-gating
description: "Decide whether an int8 or mixed-precision version of the music model is accurate enough to use by comparing it with a reference using cosine similarity and rejecting versions that fall below threshold."
version: 0.1.0
---

# NPU Quantization and Accuracy Gating

Back to the [GesturDJ README](../../README.md).

int8 makes the model smaller and faster but can damage it. Decide before generating, not after
listening to a bad song. The gate runs one fixed test case through the NPU graphs and compares
the output with the fp32 PyTorch reference.

```
python3 diffrhythm_npu_scripts/gate_board.py ctx_a,ctx_b,ctx_b,ctx_a out.raw case      # on the board
python3 diffrhythm_npu_scripts/cosine_vs_ref.py out.raw case/ref_v.f32 --frames 960
```

| Cosine against the reference | Verdict |
| --- | --- |
| 0.999 or more | as good as fp16: generate |
| 0.99 to 0.999 | usable: generate, then listen |
| below 0.99 | too lossy: do not generate |

## Measured (Qualcomm IQ8, 44.6 s graphs)

| Setup | Cosine | Max abs error | Verdict |
| --- | --- | --- | --- |
| All fp16 | 0.99999 | 0.164 | as good as fp16 |
| Mixed: ends fp16, middle two graphs int8 | 0.99986 | 0.431 | as good as fp16 |
| All int8 (all four graphs) | 0.763 | 9.695 | **too lossy: do not generate a song** |

All-int8 graphs take fp32 inputs, so the fp16 test case is widened first with
[`make_fp32_case.py`](../../diffrhythm_npu_scripts/make_fp32_case.py) (an exact upcast). The gate rejects all-int8, which is why the
mixed setup keeps the first and last graphs in fp16.

Evidence: [`npu-accuracy-gate.log`](../../evidence/iq8-run/npu-accuracy-gate.log).

## Rules

- The thresholds do not move to pass.
- Read the max error too: cosine alone can hide a few large local errors.
- The output and reference must have the same number of values; a mismatch means the graphs and
  the test case disagree on the song length.
- Only int8 weights with 16-bit activations (w8a16) work on this model.

Complete when the cosine and verdict are recorded for each setup considered.
