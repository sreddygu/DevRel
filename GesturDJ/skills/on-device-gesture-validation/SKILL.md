---
name: on-device-gesture-validation
description: "On the machine that will run the recognizer, check that the exported model matches the original, keeps its accuracy on held-out data and runs fast enough."
version: 0.2.0
---

# On-Device Gesture Validation

Back to the [GesturDJ README](../../README.md).

Run this **on the machine that will run the recognizer** (the PC now, the board
later). It answers three questions with numbers.

```
python validate_onnx.py --data_dir DATASET --output_dir MODEL_DIR --out onnx-validation.json
python validate_onnx.py ... --no_parity        # on a board without torch
```

| Check | Pass rule | What it catches |
| --- | --- | --- |
| Parity | max abs logit difference vs the PyTorch checkpoint <= 1e-3 | an export that changed the math |
| Held-out accuracy | same seed/split as training; report the sample count | a model that only memorized training data |
| Latency | p95 of single-sample (preprocess + inference) <= 50 ms over 300+ runs | a recognizer too slow for the live path |

## Rules

- Use the **same seed and held-out fraction as training** (defaults 0 and 0.2).
- Parity needs torch. Validate it once on the PC, then use `--no_parity` on a
  board and **say it was skipped**.
- A failed check is reported with its number. Never loosen the tolerance or the
  budget to pass.
- A PC number is not a Ventuno Q number. Do not report one machine's result for another.

## Measured (PC, synthetic data)

Parity 1.19e-06; held-out accuracy 1.0 (30 samples); latency p50 0.17 ms, p95
0.75 ms. In a torch-free environment: accuracy 1.0, p95 0.31 ms.

## Measured (Qualcomm IQ8 board, synthetic data)

Torch-free, parity skipped: accuracy 1.0 (30 samples), latency p50 0.228 ms, p95
0.282 ms. Evidence: [`onnx-validation.json`](../../evidence/iq8-run/onnx-validation.json). This is an IQ8, not a Ventuno Q.

Complete when [`onnx-validation.json`](../../evidence/pc-run/onnx-validation.json) exists and a verdict names the failed check,
or says all passed on this machine.

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

- Validate my exported gesture model on the IQ8 board
- Measure inference latency of the gesture model on the device
- Does the on-device model give the same predictions as on my PC?
- Run the held-out accuracy check on the board
- Is my gesture model fast enough for live use?
- Write the on-device validation record for my gesture model

<!-- skills-hub:end -->
