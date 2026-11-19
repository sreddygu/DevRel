# MobileNetV2 NPU/CPU Benchmark on IQ-9075 — Architecture

## Overview

Benchmarks MobileNetV2 on the Dragonwing IQ-9075 EVK (QCS9075), reachable
over adb (USB) or ssh (Wi-Fi). CPU inference produces real, measured
numbers. NPU (Hexagon HTP v73) has two independent code paths with two
independent statuses — see README's "Two independent NPU/GPU code paths"
table. GPU shares the plugin-EP path's blocker and has not been
retested via the context-binary path.

## Target Platform

- **Board:** Dragonwing IQ-9075 EVK
- **SoC:** QCS9075 (Hexagon HTP V73, ~100 dense TOPS)
- **Interface:** `adb` over USB-C, or `ssh`/`scp` over Wi-Fi

## System Diagram

```
Host (Windows)                          Board (IQ-9075)
─────────────────                       ──────────────────────
run_iq9075.py
  preprocess test_input.jpg               transport: adb (USB) or ssh (Wi-Fi)
  push (model, .npy, NHWC raw,          →  /data/local/tmp/quad/...
        labels, script, [context .bin])
  invoke deploy/inference.py              deploy/inference.py
    (adb shell / ssh exec)                    │
                                    ┌──────────┼──────────────┐
                                    │   CPU    │  onnxruntime_qnn   │  qnn-net-run +
                                    │  (real)  │  plugin EP (NPU/GPU│  context binary
                                    │          │  attempt, blocked  │  (real NPU pass,
                                    │          │  on this board)    │  --qnn-context-bin
                                    └──────────┴─────────────────────┘
  ← stdout (JSON)
print_result()
```

## Components

| Component | File | Description | Dependencies |
|---|---|---|---|
| Host orchestrator | `run_iq9075.py` | transport-agnostic (adb/ssh) discovery, preprocess (2 input formats), push, invoke, parse, print | numpy, Pillow, `quad_mcp_client.local.board.ssh` (SSH transport) |
| On-device inference | `deploy/inference.py` | CPU benchmark (real), plugin-EP NPU/GPU attempt (honest), context-binary NPU pass via `qnn-net-run` (real, when supplied) | onnxruntime, onnxruntime_qnn (both paths optional/independent) |
| Test suite | `tests/` | Host-side unit + smoke + end-to-end tests | pytest |

## Model Card

- **Model (CPU/plugin-EP path):** MobileNetV2, ONNX Model Zoo export (opset 12)
- **Model (context-binary NPU path):** AI Hub Models catalog `mobilenet_v2` checkpoint, compiled to a QNN context binary (QAIRT 2.45.0 target) — a **different checkpoint**, not the same weights as the ONNX export above; see the caveat in README/the debugging report before comparing latencies across paths
- **Task:** ImageNet classification (1000 classes)
- **Input (ONNX/CPU/plugin-EP):** `(1, 3, 224, 224)` float32, NCHW, ImageNet-normalized
- **Input (context binary):** `(1, 224, 224, 3)` float32, NHWC, `[0,1]`-range — per the binary's exported `metadata.json`
- **Output:** `(1, 1000)` float32 logits (both paths)

## Deployment

`run_iq9075.py --transport {adb,ssh} [--serial <s> | --host <ip>]`
handles the full push (individual file pushes, never a directory) and
on-device invocation for whichever transport the board supports.

## KPIs

Verified latency numbers, environment pinning, and reproduction
commands live in
[`docs/debugging/8. NPU_Profiling_MobileNetV2_IQ9075.md`](../../docs/debugging/8.%20NPU_Profiling_MobileNetV2_IQ9075.md)
(local source of truth — not committed to the public repo). Summary:

| Backend | Latency (mean) | Throughput |
|---|---|---|
| CPU (`onnxruntime`, ONNX Model Zoo export) | ~24–35 ms (session/version/load-dependent — always check the reported `onnxruntime.__version__` alongside any number) | ~28–41 FPS |
| NPU (Hexagon HTP v73, `qnn-net-run` + AI Hub context binary) | ~2.5–2.7 ms | ~325–350 FPS |
| NPU/GPU, `onnxruntime_qnn` plugin EP | N/A | Structurally blocked on this board's Linux device layout — not a bug in this app |

## Known limitations

- `onnxruntime_qnn` plugin-EP NPU/GPU attempt is blocked by a Linux
  device-discovery gap in `onnxruntime` itself, unrelated to QAIRT
  version — no workaround from this client.
- The context-binary NPU path has only been exercised with an HTP
  (NPU)-targeted binary; GPU has not been retested this way.
- No power/thermal profiling — `qnn-net-run --perf_profile burst` was
  used (maximizes clocks, not representative of sustained/efficiency
  power draw).
