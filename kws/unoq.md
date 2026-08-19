# Arduino UNO Q (Debian MPU) — Run Keyword Spotting (KWS) with a USB Mic

This repo includes a PyTorch KWS model notebook (`pytorch_keyword_spotting.ipynb`) plus a Debian-friendly streaming demo script (`kws_keyword_beep_onnx.py`) that listens for a keyword and plays a beep when detected (recommended on UNO Q).

## 1) Train + export (on your dev machine)

1. Open `pytorch_keyword_spotting.ipynb` and run all cells.
2. Confirm the export step writes to `output/`:
   - `output/pytorch_kws_model.pt`
   - `output/pytorch_kws_labels.json`

## 2) Copy to UNO Q (Debian)

Copy the demo script + exported artifacts to the UNO Q.

### From Windows (PowerShell)

Set your UNO Q SSH target once, then use `scp`.

```powershell
$UNOQ = "arduino@<UNO_Q_HOST>"  # hostname or IP
```

If your Windows path gets mis-parsed by `scp`, either `cd` into the repo or use the stop-parsing operator `--%`.

Option A (cd first):
```powershell
cd "<path-to-this-repo>\\kws"
scp kws_keyword_beep_onnx.py $UNOQ:~/
scp -r output $UNOQ:~/output
```

Option B (stop parsing):
```powershell
scp --% "<path-to-this-repo>\\kws\\kws_keyword_beep_onnx.py" $UNOQ:~/
scp --% -r "<path-to-this-repo>\\kws\\output" $UNOQ:~/output
```

## 3) Set up Python on UNO Q (Debian)

SSH in:
```bash
ssh arduino@<UNO_Q_HOST>
```

Install system dependencies:
```bash
sudo apt-get update
sudo apt-get install -y python3-venv portaudio19-dev alsa-utils
```

Create a virtual environment (PEP 668-friendly) and install Python packages:
```bash
python3 -m venv ~/kws-venv
~/kws-venv/bin/pip install numpy librosa sounddevice torch
```

## 4) Verify audio devices (USB camera mic)

List capture + playback devices:
```bash
arecord -l
aplay -l
```

Typical working devices we observed:
- USB camera mic: `plughw:1,0`
- Speaker out: `plughw:0,3`

### Mic capture sanity check (recommended)
```bash
arecord -D plughw:1,0 -f S16_LE -c 1 -r 16000 -d 3 test.wav
```

Optional playback check:
```bash
aplay -D plughw:0,3 test.wav
```

## 5) Run streaming KWS (keyword -> beep)

### Option A (Recommended on UNO Q): ONNX Runtime (no PyTorch)

If `import torch` fails on the UNO Q (e.g., `Illegal instruction`), run KWS using ONNX Runtime.

#### Why ONNX instead of PyTorch on UNO Q?
On UNO Q, `torch` can crash at import time with `Illegal instruction` (SIGILL) when the installed PyTorch wheel was compiled with CPU instruction set assumptions that don’t match the UNO Q CPU. ONNX Runtime runs the exported model without PyTorch, avoiding that compatibility issue (and it’s typically smaller/lighter for inference).

#### 1) Export ONNX on your dev machine (where PyTorch works)

From the repo:
```bash
python export_pytorch_to_onnx.py --pt output/pytorch_kws_model.pt --labels output/pytorch_kws_labels.json
```

This writes:
- `output/pytorch_kws_model.onnx`
- `output/pytorch_kws_model.onnx.data` (may be present for external weights; copy it if it exists)
- `output/pytorch_kws_config.json`
- `output/pytorch_kws_labels.json`

Copy those to the UNO Q `~/output/` folder.

#### 2) Install runtime deps on UNO Q (Debian)

```bash
sudo apt-get update
sudo apt-get install -y python3-venv portaudio19-dev alsa-utils
python3 -m venv ~/kws-venv
~/kws-venv/bin/pip install numpy sounddevice onnxruntime
```

#### 3) Run

List valid labels:
```bash
~/kws-venv/bin/python ~/kws_keyword_beep_onnx.py --output-dir ~/output --list-labels
```

List available mic devices (PortAudio):
```bash
~/kws-venv/bin/python -c "import sounddevice as sd; print(sd.query_devices())"
```

Notes:
- `--mic` selects a sounddevice/PortAudio input device (index like `0`/`2`, or a substring like `"USB Camera"`), not an ALSA `plughw:*` string.
- If your mic can't capture at the model sample rate (commonly 16 kHz) and you see `Invalid sample rate`, run capture at a supported rate and resample in-script via `--mic-sample-rate` (example below).

Detect a keyword (example: `yes`):
```bash
~/kws-venv/bin/python ~/kws_keyword_beep_onnx.py --output-dir ~/output --keyword yes --mic 0 --mic-sample-rate 24000 --spk default
```

Exit after the first detection:
```bash
~/kws-venv/bin/python ~/kws_keyword_beep_onnx.py --output-dir ~/output --keyword yes --mic 0 --mic-sample-rate 24000 --spk default --exit-on-detect
```

Debug what the model thinks it's hearing (prints stable detections for any label):
```bash
~/kws-venv/bin/python ~/kws_keyword_beep_onnx.py --output-dir ~/output --keyword yes --mic 0 --mic-sample-rate 24000 --spk default --print-any-detect --threshold 0.5 --stable-n 1
```

Useful tuning flags:
- `--threshold 0.8` (reduce false positives; applies to the keyword probability)
- `--stable-n 4` (require more consecutive hits)
- `--cooldown-steps 15` (avoid repeated triggers)
- `--output-dir ~/output` (if artifacts aren't in `./output`)

## Troubleshooting

### "Missing model file" / "Missing labels file"
Ensure these exist on the UNO Q:
- `~/output/pytorch_kws_model.onnx`
- `~/output/pytorch_kws_model.onnx.data` (if present)
- `~/output/pytorch_kws_config.json`
- `~/output/pytorch_kws_labels.json`

Then run with:
```bash
~/kws-venv/bin/python ~/kws_keyword_beep_onnx.py --output-dir ~/output --keyword yes --mic 0 --mic-sample-rate 24000 --spk default
```

### `pip install ...` fails with “externally-managed-environment”
Use a venv as shown above; don’t install system-wide.

### `Illegal instruction` when running the script (PyTorch)
This usually means a PyTorch wheel was built with CPU instruction set assumptions that don't match the UNO Q CPU. Use Option A (ONNX Runtime) above to run KWS without PyTorch.

### `Invalid sample rate` when opening the mic
Some USB mics only support capture rates up to e.g. 24000 Hz at the hardware layer (check with `arecord --dump-hw-params -D hw:1,0 ...`).
Use the highest supported capture rate and pass it via `--mic-sample-rate` so the script can resample to the model rate:
```bash
~/kws-venv/bin/python ~/kws_keyword_beep_onnx.py --output-dir ~/output --mic 0 --mic-sample-rate 24000 --spk default --keyword yes
```
