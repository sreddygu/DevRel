# AGENTS.md (Wake Word)

Scope: `projects/wake_word/`

## What This Project Contains

- `train_wakeword.py`: trains a PyTorch KWS model; can optionally export ONNX (`--export-onnx`).
- `export_pytorch_to_onnx.py`: exports a `.pt` checkpoint to ONNX + config JSON.
- `kws_keyword_beep_onnx.py`: streaming inference demo using ONNX Runtime.
- `speech_commands_v0.02_min/`: small Speech Commands subset used for local development.
- `output*/`: exported artifacts (model + labels + config).

## Run Commands

- Train (defaults to `speech_commands_v0.02_min/`):
  - `python3 train_wakeword.py --keyword hey_dragon --epochs 20 --out-dir output`
- Train with a full dataset path:
  - `python3 train_wakeword.py --speech-commands-dir /path/to/speech_commands_v0.02`
  - Or set `SPEECH_COMMANDS_DIR=/path/to/speech_commands_v0.02`
- Export ONNX after training:
  - `python3 train_wakeword.py --export-onnx`
  - Or separately: `python3 export_pytorch_to_onnx.py --pt output/pytorch_kws_model.pt --labels output/pytorch_kws_labels.json`
- Streaming demo help / label list:
  - `python3 kws_keyword_beep_onnx.py --output-dir output --list-labels`

## Coding Style

- Follow existing file style (4-space indentation; type hints where already used).
- Prefer explicit CLI flags rather than hard-coded paths.

