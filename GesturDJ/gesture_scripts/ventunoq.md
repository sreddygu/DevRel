# Arduino Ventuno Q (Ubuntu) - Run Gesture Recognition (IMU / time-series) with ONNX Runtime

Back to the [GesturDJ README](../README.md).

This repo supports training a small gesture recognizer in PyTorch on your dev machine, exporting to ONNX, and running inference on Ventuno Q using ONNX Runtime (no PyTorch needed).

## Why ONNX Runtime on Ventuno Q?
On some Arm boards, `import torch` crashes with `Illegal instruction` (SIGILL) when the installed PyTorch wheel was built for a different CPU instruction set. This was seen on the Arduino UNO Q and has not been checked on the Ventuno Q. ONNX Runtime runs the exported model without PyTorch, so it avoids the issue either way.

**Sensor:** the Ventuno Q's product page lists no onboard IMU. Attach a motion sensor (for example a Modulino node on the Qwiic connector) to record gestures.

## 1) Train + export (on your dev machine)

Install training deps (this now includes `onnx` and `onnxscript`, which export needs on current PyTorch):
```bash
pip install -r requirements-train-pytorch.txt
```
On Windows, a redirected console can be cp1252; the export script switches to UTF-8 itself, but if another script prints a
non-ASCII character and crashes, set `PYTHONUTF8=1`.

Train (writes `outputs/gesture_model.pt`, `outputs/gesture_config.json`, `outputs/gesture_labels.json`):
```bash
python train_gesture_pytorch.py --data_dir <DATASET_ROOT> --output_dir outputs
```

Export ONNX:
```bash
python export_gesture_pytorch_to_onnx.py --pt outputs/gesture_model.pt --labels outputs/gesture_labels.json --config outputs/gesture_config.json --onnx outputs/gesture_model.onnx
```

## 2) Copy to Ventuno Q

Set your Ventuno Q SSH target once, then use `scp`:
```powershell
$VENTUNOQ = "<user>@<VENTUNO_Q_HOST>"  # your login and the board's hostname or IP
```

Copy the inference script, the two small modules it imports, and the exported artifacts. The scripts import
[`gesture_preprocess.py`](gesture_preprocess.py) and [`gesture_io.py`](gesture_io.py) (NumPy only); **do not copy [`gesture_pytorch_model.py`](gesture_pytorch_model.py)**, it imports `torch`.
```powershell
scp predict_gesture_onnx.py gesture_preprocess.py gesture_io.py $VENTUNOQ:~/
scp -r outputs $VENTUNOQ:~/outputs
```
`outputs` must contain `gesture_model.onnx` (a single file; the export script embeds the weights), `gesture_config.json`
and `gesture_labels.json`. Optional validation on the board (accuracy and latency, no torch): also copy
[`validate_onnx.py`](validate_onnx.py) and a copy of the dataset, then run it with `--no_parity`.

Also copy at least one sample you want to classify:
```powershell
scp "<path-to-sample>\\sample.csv" $VENTUNOQ:~/sample.csv
```

## 3) Set up Python on Ventuno Q (Ubuntu)

```bash
sudo apt-get update
sudo apt-get install -y python3-venv
python3 -m venv ~/gesture-venv
~/gesture-venv/bin/pip install -r ~/outputs/requirements-onnx.txt || true
~/gesture-venv/bin/pip install numpy onnxruntime
```

## 4) Run inference on Ventuno Q

```bash
~/gesture-venv/bin/python ~/predict_gesture_onnx.py --output_dir ~/outputs --input ~/sample.csv --topk 3
```

