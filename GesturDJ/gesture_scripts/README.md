# Gesture Recognition (IMU / time-series)

Back to the [GesturDJ README](../README.md).

Train a gesture recognizer on 3-axis time-series (e.g., accelerometer `ax,ay,az`) and run inference on embedded Linux devices (Arduino Ventuno Q) using ONNX Runtime.

Scripts (scikit-learn baseline):
- [`train_gesture.py`](train_gesture.py): train + export `joblib` model
- [`predict_gesture.py`](predict_gesture.py): predict a single file

Scripts (PyTorch + ONNX Runtime):
- [`train_gesture_pytorch.py`](train_gesture_pytorch.py): train + export `outputs/gesture_model.pt` + `outputs/gesture_config.json`
- [`export_gesture_pytorch_to_onnx.py`](export_gesture_pytorch_to_onnx.py): export `outputs/gesture_model.onnx`
- [`predict_gesture_onnx.py`](predict_gesture_onnx.py): predict using ONNX Runtime (no `torch` required)
- [`ventunoq.md`](ventunoq.md): end-to-end steps for Ventuno Q / Ubuntu

Utilities:
- [`make_synthetic_dataset.py`](make_synthetic_dataset.py): generate a local starter dataset
- [`download_dataset_uwave.py`](download_dataset_uwave.py): optional downloader/converter (may be blocked by proxies)

## Data format

Point the trainer at a dataset root directory with one subfolder per label:

```
DATASET_ROOT/
  swipe_left/
    sample_0001.csv
    sample_0002.csv
  swipe_right/
    sample_0001.csv
  circle/
    sample_0001.csv
```

Each sample file can be:
- `.csv` with columns `ax, ay, az` (recommended), or `x, y, z`, or any 3 numeric columns (first 3 are used)
- `.npy` containing an array shaped `(T,3)`

## Setup

```
pip install -r requirements.txt
```

For PyTorch training:
```
pip install -r requirements-train-pytorch.txt
```

For ONNX Runtime inference (e.g., Ventuno Q):
```
pip install -r requirements-onnx.txt
```

## Quickstart (no real dataset needed)

```
python make_synthetic_dataset.py --data_dir gesture_data/synthetic
python train_gesture.py --data_dir gesture_data/synthetic --output_dir outputs
```

## Train

```
python train_gesture.py --data_dir C:\path\to\dataset --output_dir outputs
```

Outputs:
- `outputs/gesture_model.joblib`
- `outputs/gesture_labels.json`

## Train (PyTorch) + export ONNX

Train:
```
python train_gesture_pytorch.py --data_dir C:\path\to\dataset --output_dir outputs
```

Export ONNX:
```
python export_gesture_pytorch_to_onnx.py --pt outputs/gesture_model.pt --labels outputs/gesture_labels.json --config outputs/gesture_config.json
```

Outputs:
- `outputs/gesture_model.pt`
- `outputs/gesture_config.json`
- `outputs/gesture_model.onnx`
- `outputs/gesture_labels.json`

## Predict a single file

```
python predict_gesture.py --model outputs/gesture_model.joblib --labels outputs/gesture_labels.json --input C:\path\to\file.csv
```

## Predict a single file (ONNX Runtime)

```
python predict_gesture_onnx.py --output_dir outputs --input C:\path\to\file.csv
```

## Quick smoke test (no dataset needed)

```
python smoke_test.py
```

## Get a starter dataset (downloads into this project)

This downloads the uWave gesture dataset (UCR archive) and converts it into the folder-per-label CSV format expected by [`train_gesture.py`](train_gesture.py). This may fail behind some corporate proxies.

```
python download_dataset_uwave.py --data_dir gesture_data/uwave
```

Then train:

```
python train_gesture.py --data_dir gesture_data/uwave --output_dir outputs
```

## No dataset yet?

The `C:\path\to\dataset` in the examples is a placeholder. If you don't have real sensor data yet, you can generate a small synthetic dataset inside this project and train on it:

```
python make_synthetic_dataset.py --data_dir gesture_data/synthetic
python train_gesture.py --data_dir gesture_data/synthetic --output_dir outputs
```

If you download a uWave zip manually, you can convert it locally:

```
python download_dataset_uwave.py --zip_path C:\path\to\UWaveGestureLibraryAll.zip --data_dir gesture_data/uwave
```

## Added for the GesturDJ skills

Read-only helpers, each one operation with a meaningful exit code:
- [`discover_host.py`](discover_host.py): OS, real CPU architecture (detects x64 Python emulated on an ARM64 PC), Python, packages, disk, audio players.
- [`check_dataset.py`](check_dataset.py): per-label counts and lengths; flags too few samples, imbalance, NaN/inf, flat series. Exit 1 on error.
- [`live_mixer.py`](live_mixer.py) and [`make_test_clips.py`](make_test_clips.py): replay recorded sensor windows through the recognizer and a mix map, switch the playing clip and time each stage; the second writes stand-in clips.
- [`probe_audio_output.py`](probe_audio_output.py): list the sound card and players and time each player at the default and a small buffer.
- [`warm_output.py`](warm_output.py) and [`probe_warm_stream.py`](probe_warm_stream.py): a PipeWire output stream kept open and fed in real time (use it with `live_mixer.py --player warm`), and a probe comparing it with a player started per gesture.
- [`probe_hw_latency.py`](probe_hw_latency.py): driver-level start latency of the audio output (polls the ALSA PCM until it is running), run on the board.
- [`validate_live_latency.py`](validate_live_latency.py): replay many gestures and check the estimated gesture-to-sound time against the budget.
- [`validate_onnx.py`](validate_onnx.py): parity vs the PyTorch checkpoint, held-out accuracy using the training split, single-sample latency vs a budget. `--no_parity` on a board without torch.
- [`gesture_preprocess.py`](gesture_preprocess.py): the NumPy-only preprocessing, split out of [`gesture_pytorch_model.py`](gesture_pytorch_model.py) so the ONNX scripts never import `torch`. [`gesture_pytorch_model.py`](gesture_pytorch_model.py) re-exports it, so training code is unchanged.

Changed: [`export_gesture_pytorch_to_onnx.py`](export_gesture_pytorch_to_onnx.py) (UTF-8 output; embeds the weights so the result is one file), [`requirements-train-pytorch.txt`](requirements-train-pytorch.txt) (adds `onnx`, `onnxscript`), [`ventunoq.md`](ventunoq.md) (full copy list). Why: see [`../evidence/pc-run/`](../evidence/pc-run/).

