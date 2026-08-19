# KWS (Keyword Spotting)

Train a small keyword-spotting model on Google Speech Commands and run a streaming “keyword → beep” demo (including a PyTorch-free ONNX Runtime path for embedded Linux devices like Arduino UNO Q).

This repo contains:
- `pytorch_keyword_spotting.ipynb`: a PyTorch notebook that builds a small CNN (and optional depthwise-separable CNN) on log-mel spectrogram features.
- `export_pytorch_to_onnx.py`: export the PyTorch checkpoint to ONNX + a small config JSON.
- `kws_keyword_beep_onnx.py`: streaming demo that runs inference with ONNX Runtime (no `torch`).
- [unoq.md](unoq.md): end-to-end steps for running the demo on UNO Q / Debian.

## Prerequisites
- Python 3.10+ recommended
- Speech Commands v0.02 extracted locally

## Setup
1. Download and extract the dataset so the folder contains `validation_list.txt`, `testing_list.txt`, and label subfolders with `.wav` files.
2. Point the notebook at the dataset root by either:
   - setting an env var: `SPEECH_COMMANDS_DIR=/path/to/speech_commands_v0.02`
   - or editing `SPEECH_COMMANDS_DIR` in the notebook.

## Run
Open `pytorch_keyword_spotting.ipynb` and run all cells top-to-bottom.

## Outputs
Notebooks export:
- PyTorch: `output/pytorch_kws_model.pt`, `output/pytorch_kws_labels.json`
