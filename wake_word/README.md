# Wake Word (Keyword Spotting): `hey_dragon`

Train, export, and run a streaming keyword spotter for the `hey_dragon` wake word.

## What’s Here

- Training: `pytorch_keyword_spotting.ipynb` (PyTorch notebook)
- (Optional) Export: `export_pytorch_to_onnx.py` (PyTorch -> ONNX + config)
- Streaming demo: `kws_keyword_beep_onnx.py` (ONNX Runtime)

## Dataset (required for good false-positive behavior)

Training needs **negatives** (non-keyword words) to learn `_unknown_`. If your dataset
root only contains `hey_dragon/` + `_background_noise_/`, you’ll usually get a
trigger-happy model (false detects on random speech).

You have two options:

- Use a full Speech Commands dataset root (recommended), or
- Build a small subset that includes `hey_dragon/`, a handful of negative word folders
  (e.g. `yes/`, `no/`, `up/`, `down/`), `_background_noise_/`, and the split lists.

The scripts expect Speech Commands-style structure (word folders, `_background_noise_`,
and the split list files `validation_list.txt` / `testing_list.txt`).

## Train

Training is done in the notebook:

- `projects/wake_word/pytorch_keyword_spotting.ipynb`

## (Optional) Export ONNX

After notebook training, export either:

```bash
python3 export_pytorch_to_onnx.py --help
python3 export_pytorch_to_onnx.py --pt output/pytorch_kws_model.pt --labels output/pytorch_kws_labels.json
```

## Streaming Demo

```bash
python3 kws_keyword_beep_onnx.py --help
python3 kws_keyword_beep_onnx.py --output-dir output --list-labels
```

## Run The Notebook On UNOQ4 (quick notes)

- Pyenv:
  - `pyenv install 3.11.15`
  - `cd projects && pyenv local 3.11.15 && python --version`
- Create venv + install notebook:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install notebook`
- Start Jupyter on UNOQ4:
  - `cd ~/qa-intermediate-curriculum/projects/wake_word`
  - `source .venv/bin/activate`
  - `python -m notebook --ip 0.0.0.0 --port 8888 --no-browser`
- Arduino CLI / RPC notes (when flashing MCU sketches like `rpc_hearts`):
  - Don’t run `arduino-cli` under `sudo` unless you also installed the core for `root` (otherwise you can hit `Platform 'arduino:zephyr' not found`).
  - If `arduino-router` is running, stop it before upload (it may hold `/dev/ttyHS1`):
    - `sudo systemctl stop arduino-router`
  - Prefer uploading via the UNOQ network port when it shows up in `arduino-cli board list`:
    - `arduino-cli upload -p <IP_FROM_BOARD_LIST> --fqbn arduino:zephyr:unoq .`
  - After flashing, restart the router:
    - `sudo systemctl start arduino-router`

## Verification status (2026-11-27)

The `hey_dragon` recordings are not in this repo, so the pipeline was exercised end to end with the stand-in
keyword `marvin` from Speech Commands v0.02 (`train_wakeword.py --keyword marvin`); nothing here is a `hey_dragon` result.

- `train_wakeword.py` (x64 Python 3.11, torch 2.15 CPU, 5 epochs, about 6 minutes) -> ONNX export -> `kws_keyword_beep_onnx.py --list-labels` all run;
  PyTorch and ONNX logits agree (max difference 1.3e-5).
- **Bug fixed:** training used raw log-mel features while the notebook and `kws_keyword_beep_onnx.py` standardize each clip, so a model trained by
  the script almost never triggered in the demo (3% recall). `train_wakeword.py` now standardizes per clip too. Retrained: held-out `marvin` recall
  59/60 with the demo's features. The 5-epoch model is still weak (validation accuracy 0.75, about 50% false accepts on other words), so train longer
  on more negatives before relying on it.
- The detection loop reads a live microphone only, so it was run on a synthetic 8 s stream through the demo's own feature code instead of a mic.
- PyPI has no PyTorch wheel for Windows ARM64 on Python 3.12; use an x64 Python (emulated) or Linux/WSL.
- Not run: the notebook, `unoq.md` (UNO Q), `build_dlc.py`.
