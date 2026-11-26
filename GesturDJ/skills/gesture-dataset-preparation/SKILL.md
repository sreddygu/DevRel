---
name: gesture-dataset-preparation
description: "Choose and prepare a labelled motion dataset for gesture recognition (synthetic, public or your own capture), check its quality and split it for training."
version: 0.2.0
---

# Gesture Dataset Preparation

Back to the [GesturDJ README](../../README.md).

Decide what data the recognizer will learn from, and whether it is good enough,
before training. Layout expected by the trainers:

```
DATASET_ROOT/
  left/   sample_00000.csv ...   (columns ax,ay,az; or x,y,z; or first 3 numeric)
  right/  ...
  circle/ ...
```

## Steps

1. **Pick the source** with the developer:
   - *Synthetic* (fastest; proves the pipeline): `make_synthetic_dataset.py
     --data_dir <ABSOLUTE PATH> --samples_per_label 50`. A relative path is
     resolved against the script's folder, not your current folder.
   - *Public dataset* (uWave): [`download_dataset_uwave.py`](../../gesture_scripts/download_dataset_uwave.py). **Unverified**: on
On the test PC the UCR link returned 404 and the other host 403 from a corporate
     network. Show the license first; if it fails, say so and offer another source.
   - *Own capture:* needs `imu-capture` (not written yet). Ask before recording.
2. **Check** with `check_dataset.py --data_dir <path> --out dataset-report.json`.
   Exit 1 means an error (fewer than 2 labels, a label under 5 samples, NaN/inf).
   Show warnings (under 20 samples per label, class imbalance above 3x, flat
   series, series shorter than 16 points) to the developer.
3. **Decide** and write the decision with reasons: `usable`, `needs more data`
   (say how many per label), or `not usable`.

## Limits

Synthetic data is easy: the PyTorch model scored 1.0 on 30 held-out samples. That
shows the code path works, not that a real wrist movement will be recognized. Say
this in the decision.

Complete when [`dataset-report.json`](../../evidence/pc-run/dataset-report.json) exists, `ok` is true, warnings were shown, and
the decision is recorded. This skill never trains a model and never edits the
developer's files.

<!-- skills-hub:begin -->

## Compatibility

| Item | Details |
| --- | --- |
| Devkits | Not device-specific |
| Target OS | No target OS constraint declared |
| Host OS | Windows, Linux (or WSL) |
| Requirements | Python 3.10+; PC and Qualcomm IQ8 board (Qualcomm Linux 2.0); QAIRT for the NPU music path |

References: [GesturDJ README](https://github.com/sreddygu/DevRel/blob/main/GesturDJ/README.md), [IQ8 SSH runbook](https://github.com/sreddygu/DevRel/blob/main/GesturDJ/ACE-Step/IQ8_SSH_RUNBOOK.md).

## Example prompts

- Prepare a synthetic accelerometer dataset for left, right and circle gestures
- Check my gesture recordings for class imbalance, flat series and bad samples
- Split my motion data into train and held-out sets
- Which gesture dataset should I start with?
- Is my dataset good enough to train on, or do I need more samples per label?
- Download the public uWave gesture dataset after showing me its license
- Generate dataset-report.json and explain the warnings

<!-- skills-hub:end -->
