# UNO Q Wake-Word Runbook

Last updated: October 5, 2026

Run the `hey_dragon` ONNX wake-word model on an Arduino UNO Q from a VS Code Remote SSH session.

## Prerequisites

- The UNO Q is reachable over SSH.
- The curriculum repository is present at `~/qa-intermediate-curriculum`.
- This project and its `output/` model artifacts are present at `~/qa-intermediate-curriculum/projects/wake_word`.

## Connect From VS Code

1. Install the VS Code **Remote - SSH** extension on the development computer.
2. Press `Ctrl+Shift+P`, then select **Remote-SSH: Connect to Host**.
3. Connect to the UNO Q using its configured SSH host.
4. Open the remote folder `~/qa-intermediate-curriculum/projects/wake_word`.
5. Open the integrated remote terminal with ``Ctrl+` ``.

## Check The Model Labels

UNO Q runs Linux. Use Linux paths (`output`), not Windows paths such as `.\output`.

```bash
cd ~/qa-intermediate-curriculum/projects/wake_word
source .venv/bin/activate
python --version
python kws_keyword_beep_onnx.py --output-dir output --list-labels
```

Expected labels:

```text
_silence_
hey_dragon
_unknown_
```

## Create A Runtime Environment If Needed

If `.venv` is missing or cannot import the inference dependencies, create a separate board-local environment:

```bash
python3 -m venv ~/kws-venv
source ~/kws-venv/bin/activate
python -m pip install --upgrade pip
python -m pip install numpy sounddevice onnxruntime
cd ~/qa-intermediate-curriculum/projects/wake_word
python kws_keyword_beep_onnx.py --output-dir output --list-labels
```

## Run Live Detection

First identify the UNO Q audio devices:

```bash
arecord -l
aplay -l
```

Run the detector using the known UNO Q-style ALSA device names. Adjust `CARD` and `DEV` to match the preceding device lists when necessary.

```bash
python kws_keyword_beep_onnx.py \
  --output-dir output \
  --keyword hey_dragon \
  --alsa-device plughw:CARD=Seri,DEV=0 \
  --spk plughw:CARD=Seri,DEV=0 \
  --threshold 0.55 \
  --stable-n 1 \
  --print-rms \
  --print-keyword-prob
```

Say `hey dragon`. A successful detection prints `DETECTED KEYWORD: hey_dragon` and plays a short beep. Press `Ctrl+C` to stop the detector.

## Quick Troubleshooting

- If ALSA cannot capture at 16 kHz, use `plughw:` instead of `hw:` so ALSA can resample.
- If the mic is too quiet or treated as silence, try `--silence-rms-threshold 0.005` or `--silence-rms-threshold 0.03`.
- To reduce false positives, increase `--threshold`, use `--stable-n 4`, and add `--cooldown-steps 15`.
- Run `python kws_keyword_beep_onnx.py --help` to view all available options.
