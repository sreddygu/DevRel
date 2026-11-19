# Agent run log: GesturDJ build journey on an IQ8 board

A coding assistant (Claude) acted as the hosting agent and followed `gesturdj-agent` and `gesturdj-build-journey` by hand. One run, one assistant, one board. It is not an independent agent framework and not an automated router.

Intent: "verify the GesturDJ skills on the connected IQ8, then work on what is pending."

| # | Checkpoint | Skill or tool | Gate | Result |
| --- | --- | --- | --- | --- |
| 1 | Inject context documents | `gesture-event-contract`, `p3-self-service-boundaries` | none | Rules loaded: no stored credentials, ask before changing a device |
| 2 | Discover host and board | `device-and-host-discovery` | none (read-only) | aarch64, Qualcomm Linux 2.0, Python 3.14.4, camera and audio present, no onnxruntime, no pip, no venv |
| 3 | Present plan: install onnxruntime, copy scripts and model, validate | agent | approval requested, granted by the developer | Wheels copied from the PC |
| 4 | Validate on the board | `on-device-gesture-validation` | approved | accuracy 1.0, p95 0.28 ms, parity skipped |
| 5 | Add pip and venv | agent | approval requested, granted | First attempt (download and run `get-pip.py` on the board) was **blocked by the permission layer** and not retried. Recovery: copy the missing pure-Python modules from CPython source on the PC; then `venv` and `pip install` worked |
| 6 | Rerun from the venv | discover, `check_dataset`, `predict_gesture_onnx`, `validate_onnx` | approved | all passed (`onnx-validation-venv.json`) |
| 7 | Cross-machine parity | `model-export-and-deployment` check | none | PC and board logits for 150 samples differ by at most 2.4e-07; same top label 150 of 150 (`cross-machine-parity.json`) |
| 8 | Design the live mix | `gesture-to-live-mix-design` | none | `mix_map.json` with 3 gestures |
| 9 | Run the live mixer | `live_mixer.py` | approved (writes clips on the board) | 6 events: 4 applied, 1 debounced, 1 cooldown; worst estimated gesture-to-sound 45.7 ms against 200 ms (`live-mixer-report.json`) |
| 10 | Probe audio output | `audio-output-integration` | none | best player `aplay` with a 40 ms buffer, 112 ms median overhead; defaults 159 to 237 ms (`audio-output-probe.json`) |
| 11 | Validate the live path | `live-mixer-and-latency-validation` | none | 200 replayed gestures: p95 52.8 ms (configured buffer), 145.3 ms (process-level overhead), 511 ms (500 ms buffer) (`live-latency-*.json`); superseded by checkpoint 15 |
| 12 | NPU readiness | `music-model-npu-deployment` | read-only | cdsp running, 0 aborts, 8 of 8 binaries, no stale server (`npu-deployment-preflight.txt`) |
| 13 | Accuracy gate on the NPU | `npu-quantization-and-accuracy-gating` | approved (runs the NPU) | fp16 cosine 0.99999, mixed 0.99986; all-int8 cosine 0.763, rejected after widening the test case to fp32 (`npu-accuracy-gate.log`) |
| 14 | Generate and check a clip library | `library-generation-and-quality-evaluation` | approved (runs the NPU about 10 minutes per clip) | 2 new clips; 3 clips pass; loop seams 4 to 17 dB (`clip-library-report.json`) |
| 15 | Driver-level and speaker-level latency | `audio-output-integration`, `live-mixer-and-latency-validation` | none | Cold player start reaches the hardware at 236 to 280 ms, so the live path p95 is 260.6 ms and **fails** the 200 ms budget; the earlier 145 ms was not an upper bound. Speaker level not possible: no speaker or microphone attached (`hw-latency.json`, `live-latency-driver-level.json`) |
| 16 | Warm output stream | `audio-output-integration`, `live-mixer-and-latency-validation` | approved (board audio) | Built `warm_output.py`; warm stream 37 ms p50 / 59 ms max to a null sink vs 116 to 132 ms for a player per gesture; live path p95 112.6 ms **passes** (`warm-stream.json`, `live-latency-warm.json`, `warm-hw-status.txt`). A first version hid a 164 ms backlog in the pipe; fixed by capping it |

Not done, and why:

- Real sensor data: the IQ8 has no motion sensor, and the public dataset download returned HTTP 403.
- Arduino Ventuno Q: no board available.
- Speaker-level latency: this IQ8 has no speaker or microphone attached, so only the driver level was measured; nobody listened.
- Speaker-level confirmation of the warm stream: it was measured into a null sink plus the hardware queue, not at a speaker.
- Resume after interruption: not exercised.
