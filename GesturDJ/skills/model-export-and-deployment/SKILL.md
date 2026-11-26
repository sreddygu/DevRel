---
name: model-export-and-deployment
description: "Export a trained PyTorch gesture model to a single-file ONNX model that a board without PyTorch can load, prove it matches the original and package it."
version: 0.2.0
---

# Model Export and Deployment

Back to the [GesturDJ README](../../README.md).

Turn the PyTorch checkpoint into one ONNX file that a board with only `numpy` and
`onnxruntime` can run.

## Steps

1. **Check the host** can export: `torch`, `onnx` and `onnxscript` import
   ([`requirements-train-pytorch.txt`](../../gesture_scripts/requirements-train-pytorch.txt) now lists them).
2. **Export:** `export_gesture_pytorch_to_onnx.py --pt ... --labels ... --config ...
   --onnx ...`. The script switches output to UTF-8 and embeds the weights, so the
   result is **one** `.onnx` file (about 160 KB).
3. **Check the file set** to deploy, and nothing else:
   `gesture_model.onnx`, `gesture_config.json`, `gesture_labels.json`,
   [`predict_gesture_onnx.py`](../../gesture_scripts/predict_gesture_onnx.py), [`gesture_preprocess.py`](../../gesture_scripts/gesture_preprocess.py), [`gesture_io.py`](../../gesture_scripts/gesture_io.py).
   [`gesture_pytorch_model.py`](../../gesture_scripts/gesture_pytorch_model.py) is **not** deployed: it imports `torch`.
4. **Prove it loads without torch** in an environment with only numpy and
   onnxruntime (the PC test venv, or the board).
5. **Hand over to on-device-gesture-validation.** Copying to a board needs the
   developer's approval; the board needs `numpy` and `onnxruntime` only. Never
   import `torch` on a Ventuno Q.

## Failures seen on a fresh PC install

| Symptom | Cause | State |
| --- | --- | --- |
| `No module named 'onnxscript'` at export | requirements did not list `onnx`/`onnxscript` | fixed in requirements |
| `UnicodeEncodeError ... \u2705` | redirected Windows console is cp1252 | fixed in export script |
| board: `...onnx.data` not found | weights in a side file | fixed: embedded |
| torch-free predict: `No module named 'torch'` | shared module imported torch | fixed: [`gesture_preprocess.py`](../../gesture_scripts/gesture_preprocess.py) |

Complete when a single `.onnx` exists and a torch-free predict returns a label.
Correctness is judged by the next skill, not this one.

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

- Export my gesture model to ONNX for the IQ8 board
- Check that the ONNX output matches the PyTorch model
- Package the model so a board without PyTorch can run it
- Copy the exported model and its preprocessing script to my device
- Why is my exported ONNX model split into several files?
- Export my gesture model for the Arduino VENTUNO Q

<!-- skills-hub:end -->
