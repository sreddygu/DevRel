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
