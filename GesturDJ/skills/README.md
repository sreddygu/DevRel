# GesturDJ Synapse Skill Catalog

Back to the [GesturDJ README](../README.md).

Gestures (accelerometer on a board, or camera with pose) change music live; a music model fills a clip library in the background. Target persona: **P3, Independent Developers** (makers, hobbyists, students, community builders; public self-service; community support).

Status: **enabled pilot**. Steps 1 to 5 of the build journey were run by hand on **one PC** in a clean virtual environment; evidence is in [`../evidence/pc-run/`](../evidence/pc-run/). Steps 4 and 5 (export check, on-device validation) were then repeated on a Qualcomm IQ8 board; evidence is in [`../evidence/iq8-run/`](../evidence/iq8-run/). Nothing has been run on a Ventuno Q or on real sensor data, and the only hosting-agent run is one assistant following the skills by hand ([`../evidence/iq8-run/agent-run-log.md`](../evidence/iq8-run/agent-run-log.md)). Design and findings: [`../GESTURDJ_SYNAPSE_SKILLS.md`](../GESTURDJ_SYNAPSE_SKILLS.md). The standardized discovery catalog is [`synapse-skill-catalog.json`](synapse-skill-catalog.json); reuse classes and baseline metrics are in [`REUSE_AND_METRICS.md`](REUSE_AND_METRICS.md). Check the catalog with `python validate_skills.py` (it also checks that cited evidence files exist and that normalized metadata remains consistent).

## Written

What each skill is for, what has been run and where, and its status. Evidence for every row is in [`../evidence/`](../evidence/); the IQ8 rows are in [`../evidence/iq8-run/`](../evidence/iq8-run/). None of it has run on an Arduino Ventuno Q, on real sensor data, or measured at a speaker.

| Layer | ID | Use when | Result | Status |
| --- | --- | --- | --- | --- |
| Agent | [`gesturdj-agent`](gesturdj-agent/SKILL.md) | Open-ended request; plans, gates, checkpoints | Run once, with a coding assistant as the host; 15 checkpoints logged | Partly done |
| Journey | [`gesturdj-build-journey`](gesturdj-build-journey/SKILL.md) | From no setup to a validated recognizer; reruns | Steps 1-5 on a PC, repeated on the IQ8, plus the live mixer | Partly done |
| Domain | [`device-and-host-discovery`](device-and-host-discovery/SKILL.md) | First step: hardware and where each stage runs | PC and IQ8 | Ran |
| Domain | [`gesture-dataset-preparation`](gesture-dataset-preparation/SKILL.md) | Choose and check the data | PC and IQ8 (synthetic data) | Ran |
| Domain | [`gesture-model-training-and-evaluation`](gesture-model-training-and-evaluation/SKILL.md) | Train, read the result carefully | PC only (needs torch) | Ran (PC only) |
| Domain | [`model-export-and-deployment`](model-export-and-deployment/SKILL.md) | One-file ONNX a torch-free board can load | PC and IQ8; logits match to 2.4e-07 | Ran |
| Domain | [`on-device-gesture-validation`](on-device-gesture-validation/SKILL.md) | Parity, held-out accuracy, latency where it will run | PC and IQ8; accuracy 1.0, p95 0.26 ms | Ran |
| Domain | [`gesture-to-live-mix-design`](gesture-to-live-mix-design/SKILL.md) | Gesture to live mix action, latency budget | IQ8 replay; its 45.7 ms estimate understates the audio stage | Partly done |
| Domain | [`audio-output-integration`](audio-output-integration/SKILL.md) | Find the audio sink, measure each player's overhead | Cold player start 236-280 ms at the driver level; a warm stream is 37 ms to the sink, about 100 ms worst case with the hardware queue | Ran |
| Domain | [`live-mixer-and-latency-validation`](live-mixer-and-latency-validation/SKILL.md) | Many replayed gestures against the 200 ms budget | Player per gesture: p95 261 ms, over the 200 ms budget. Warm output stream: p95 113 ms, within it. Estimates, not measured at a speaker | Ran, passes with a warm stream |
| Domain | [`music-model-npu-deployment`](music-model-npu-deployment/SKILL.md) | Is the board ready to run the music model on its NPU | IQ8 preflight clean; graphs load and run | Ran |
| Domain | [`npu-quantization-and-accuracy-gating`](npu-quantization-and-accuracy-gating/SKILL.md) | Is the int8 or mixed model accurate enough | fp16 cosine 0.99999; mixed 0.99986; all-int8 0.763, rejected | Ran |
| Domain | [`library-generation-and-quality-evaluation`](library-generation-and-quality-evaluation/SKILL.md) | Generate clips in the background, check them | 3 clips pass; loop seams 4-17 dB | Ran |
| Context | [`gesture-event-contract`](gesture-event-contract/SKILL.md) | Injected: the one event both sensing paths emit | Applied in the agent run | Done |
| Context | [`p3-self-service-boundaries`](p3-self-service-boundaries/SKILL.md) | Injected: public tools only, community support, ask before changing devices | Applied in the agent run | Done |
| MCP tools | [`mcp-tools.yaml`](mcp-tools.yaml) | 13 deterministic tools wrapping [`gesture_scripts/`](../gesture_scripts/) and [`diffrhythm_npu_scripts/`](../diffrhythm_npu_scripts/) | Each cites its evidence file; run on the IQ8 (`export_onnx` on the PC only) | Ran |

## Planned (not written)

| Layer | ID | Note |
| --- | --- | --- |
| Domain | **`pose-gesture-recognition`** | **Pointer only, per the project lead: camera/pose path, no implementation.** Must emit the event defined in `gesture-event-contract` |
| MCP tool | imu capture, camera capture, pose estimate, push artifacts, connectivity check, generate clip | Listed under `not_yet_written` in [`mcp-tools.yaml`](mcp-tools.yaml) |

## Routing

1. Inject the two context documents.
2. `gesturdj-agent` picks the smallest safe path: one domain skill, or `gesturdj-build-journey` for a multi-step request.
3. The journey stops at the first failed gate and names the failed check; a failed step never becomes an unverified success.
4. Generation is never on the live path.
