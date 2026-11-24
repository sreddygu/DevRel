---
name: gesture-event-contract
description: "The single event format that every gesture sensor (accelerometer or camera pose) must emit so that the recognizer, mixer and music path work with either."
version: 0.1.0
---

# Gesture Event Contract (context document)

Back to the [GesturDJ README](../../README.md).

Injected before any GesturDJ skill runs. Never executed.

Every sensing path (accelerometer, or camera with pose estimation) must produce
the same event so later stages do not care where it came from:

| Field | Type | Meaning |
| --- | --- | --- |
| `label` | string | Gesture name from the trained label set (for example `swipe_left`, `circle`) |
| `confidence` | float 0 to 1 | Recognizer score |
| `intensity` | float 0 to 1 | How vigorous the motion was (peak magnitude, normalized) |
| `timestamp_ms` | int | Time the gesture window ended, on the device clock |
| `source` | `imu` or `pose` | Which sensing path produced it |

IMU samples (existing recognizer): CSV with columns `ax, ay, az` (also accepts
`x, y, z` or the first three numeric columns), or `.npy` shaped `(T,3)`; dataset
layout `DATASET_ROOT/<label>/sample_*.csv`.

Latency budget (default): gesture end to first changed sound at most 200 ms.
The camera/pose path is planned and not implemented; it must meet this same
contract.
