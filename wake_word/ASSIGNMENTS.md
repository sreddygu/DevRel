
## Capstone — End-to-end Wake Word Action System

Build a complete “wake word → action” system that is usable by someone else without debugging.

### Requirements

- Train a model with at least 3 classes: `_silence_`, `hey_dragon`, `_unknown_`.
- Export ONNX and required metadata (labels + config) to `projects/wake_word/output/`.
- Provide a single, copy/pasteable run command that:
  - does streaming inference,
  - beeps on detect, and
  - triggers an action (RPC heart on UNOQ4, or a desktop fallback action if UNOQ4 is unavailable).

### Suggested milestones

- Milestone A: dataset + splits verified (counts per label per split).
- Milestone B: model trains and passes a basic confusion matrix sanity check.
- Milestone C: ONNX export works and ONNX Runtime matches PyTorch on a small sample.
- Milestone D: streaming demo runs with a tuned “silence baseline” gate.
- Milestone E (UNOQ4): RPC action triggers reliably on stable detection.

### Reliability targets (suggested)

- False triggers on silence: “near zero” over a 2-minute silent baseline in your typical room.
- Detect latency: triggers within ~1 second of speaking the wake word.
- Repeat behavior: does not double-trigger excessively (cooldown works).

### Deliverables

- `CAPSTONE_REPORT.md` containing:
  - Environment info (versions + device)
  - Dataset description (what negatives were used)
  - Final chosen runtime flags and why
  - Metrics: silent-baseline false trigger count + a short “spoken wake word” test result
- Artifacts in `output/`:
  - `pytorch_kws_model.onnx`
  - `pytorch_kws_labels.json`
  - `pytorch_kws_config.json`
- Optional: a 60–120s demo video showing silence baseline + successful trigger(s).

### Grading rubric (example)

- Correctness (40%): exports run, streaming runs, action triggers.
- Robustness (30%): false positives controlled; reasonable tuning + justification.
- Reproducibility (20%): a new user can follow instructions; clear run commands.
- Code hygiene (10%): clean flags, minimal hard-coding, readable outputs.
