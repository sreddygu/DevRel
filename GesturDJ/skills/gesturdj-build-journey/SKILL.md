# GesturDJ Build Journey

Back to the [GesturDJ README](../../README.md).

Use when the request spans several steps ("take me from nothing to a working
gesture model") or a rerun after the data changed. For one step, use that domain
skill directly.

Inject first: `gesture-event-contract`, `p3-self-service-boundaries`.

## Steps and gates

| # | Step | Skill / tool | Gate to pass before the next step |
| --- | --- | --- | --- |
| 1 | Discover the host (and board, if any) | `device-and-host-discovery` / `discover-host` | [`device-profile.json`](../../evidence/pc-run/device-profile.json) written; missing packages listed |
| 2 | Prepare data | `gesture-dataset-preparation` / `make-synthetic-dataset`, `check-dataset` | [`dataset-report.json`](../../evidence/pc-run/dataset-report.json) `ok: true`; decision recorded |
| 3 | Train | `gesture-model-training-and-evaluation` | model files exist; held-out accuracy **and count** reported |
| 4 | Export | `model-export-and-deployment` / `export-onnx` | single `.onnx`; torch-free predict returns a label |
| 5 | Validate where it will run | `on-device-gesture-validation` / `validate-onnx` | parity, held-out accuracy and latency pass, or the failed check is named |
| 6 | Design the mapping | `gesture-to-live-mix-design` | every label mapped or listed unmapped; budget adds up |
| 7 | *(planned)* Live mixer, audio output, clip library | `live-mixer-and-latency-validation`, `audio-output-integration`, `library-generation-and-quality-evaluation` | not available yet: say so |

## Rules

- **Stop at the first failed gate.** Report the failed check with its number.
  Never continue on an unverified result.
- **Reuse a finished step** only if its inputs are unchanged (same dataset
  report, seed, and package versions).
- **Approval before:** downloads, writing into non-empty folders, copying to a
  board, installing there, recording sensors, opening a camera.
- **Say which machine each result came from.** A PC result does not validate a
  Ventuno Q.
- **Camera/pose** is planned (`pose-gesture-recognition`), not implemented.

## State carried between steps

[`device-profile.json`](../../evidence/pc-run/device-profile.json), [`dataset-report.json`](../../evidence/pc-run/dataset-report.json), the model folder (with the seed and
package versions), [`onnx-validation.json`](../../evidence/pc-run/onnx-validation.json), `mix_map.json`.

## Evidence

Steps 1 to 5 were run on a PC in a clean virtual environment, with
the failures and fixes recorded under [`evidence/pc-run/`](../../evidence/pc-run/). Step 6 is design
only. The Ventuno Q and real sensor data have not been run.
