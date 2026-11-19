# Building & Profiling Apps with QUAD — MobileNetV2 on Snapdragon X Elite & Arduino UNO Q

A hands-on guide to building simple inference applications with the **QUAD**
platform, running **MobileNetV2** across **CPU, GPU, and NPU**, profiling the
performance on each backend, and applying QUAD's optimization recommendations.

---

## Contents

1. [What you'll build](#1-what-youll-build)
2. [Prerequisites](#2-prerequisites)
3. [The QUAD workflow](#3-the-quad-workflow)
4. [Sample App 1 — MobileNetV2 CPU vs GPU vs NPU on Snapdragon X Elite](#4-sample-app-1--mobilenetv2-cpu-vs-gpu-vs-npu-on-snapdragon-x-elite)
5. [Sample App 2 — MobileNetV2 on Arduino UNO Q](#5-sample-app-2--mobilenetv2-on-arduino-uno-q)
6. [Profiling results & how to read them](#6-profiling-results--how-to-read-them)
7. [Optimization recommendations](#7-optimization-recommendations)
8. [Two more simple sample apps](#8-two-more-simple-sample-apps)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. What you'll build

| App | Target | Backends profiled | Outcome |
|-----|--------|-------------------|---------|
| **MobileNetV2 Benchmark** | Snapdragon X Elite (Windows AI PC) | CPU, GPU (Adreno), NPU (Hexagon HTP) | Side-by-side latency / throughput / power table |
| **MobileNetV2 on-device** | Arduino UNO Q (QCS2210) over USB | CPU (ONNX Runtime) | On-board latency + top-K predictions |
| **GPU Inference** | Snapdragon X Elite | GPU (Adreno) | Generated C++ `libQnnGpu` inference code |
| **Whisper ASR** | Snapdragon X Elite | NPU encoder + CPU decoder | Live streaming speech-to-text |

Every app follows the same five-step QUAD pattern, so once you understand the
first one the rest are variations on a theme.

---

## 2. Prerequisites

| Requirement | Notes |
|-------------|-------|
| QUAD Client installed | See the *QUAD Client Installation Instructions* — `install.ps1` + `QUAD_MCP_TOKEN` |
| Connection verified | In Claude Code, ask **"Is this client connected to the MCP server?"** |
| Python 3.10+ | `python --version` |
| QAIRT SDK | Installed via QUAD's `install.ps1 -QairtArchive <path>` (for real NPU/GPU runs) |
| `adb` on PATH | Only for the UNO Q sample — `winget install Google.PlatformTools` |

> **Mock mode works without hardware.** You can develop and test every sample
> in `--adapter-mode mock` (no SDK or device needed), then switch to real mode
> when you have a Snapdragon target attached.

---

## 3. The QUAD workflow

Every QUAD application follows the same five-tool MCP pattern:

```
hardware_detect  →  convert_model  →  profile_workload  →  orchestrate_workload  →  generate_code
```

| Step | MCP tool / skill | What it does |
|------|------------------|--------------|
| 1. Detect | `hardware_detect` / `/quad-detect` | Find CPU, GPU, NPU, RAM, runtimes, SDK status |
| 2. Convert | `convert_model` / `/quad-convert` | ONNX → QNN/SNPE DLC, quantize to INT8 |
| 3. Profile | `profile_workload` / `/quad-profile` | Measure latency, throughput, power per backend |
| 4. Orchestrate | `orchestrate_workload` / `/quad-orchestrate` | Compare power modes; choose where each op runs |
| 5. Generate | `generate_code` / `/quad-codegen` | Emit compilable C++ / Python / JNI inference code |

The fastest way to drive this in Claude Code is natural language — for example,
*"profile MobileNetV2 on CPU, GPU and NPU and recommend the best backend"* — or
the `/quad-*` slash commands.

---

## 4. Sample App 1 — MobileNetV2 CPU vs GPU vs NPU on Snapdragon X Elite

This sample downloads MobileNetV2, converts it via the QUAD MCP server, and
benchmarks **CPU (ONNX Runtime) vs GPU (Adreno) vs NPU (Hexagon HTP)** in one
script. It lives at `samples/mobilenetv2/`.

### Build & run

```powershell
cd samples\mobilenetv2

# One-time: install sample dependencies into a local .venv
.\run.ps1

# Run the full pipeline (download → convert → benchmark all three backends)
.venv\Scripts\python.exe run_mobilenetv2.py --image test_input.jpg
```

The script will:

1. **Download** MobileNetV2 ONNX + ImageNet labels.
2. **Convert** to a QNN INT8 DLC via the QUAD MCP server (auto-spawned over
   stdio — no server to start manually).
3. **Benchmark** CPU (10 timed runs), GPU (Adreno duration benchmark), and NPU
   (`qnn-net-run --duration` with 1000+ iterations for accurate timing).
4. **Print** a side-by-side comparison table with latency, throughput, and
   estimated power.

### Useful options

```powershell
# Use your own photo, skip re-download
.venv\Scripts\python.exe run_mobilenetv2.py --image my_photo.jpg --skip-download

# Mock mode — no SDK needed (simulated conversion)
.venv\Scripts\python.exe run_mobilenetv2.py --adapter-mode mock

# SNPE DLC for Android/Linux targets
.venv\Scripts\python.exe run_mobilenetv2.py --target-sdk snpe

# Better INT8 accuracy with calibration images
.venv\Scripts\python.exe run_mobilenetv2.py --calibration .\calib_images\
```

### Doing it conversationally in Claude Code

You don't have to remember the flags. Just ask:

> *"Convert MobileNetV2 to INT8, then profile it on CPU, GPU and NPU on my
> Snapdragon X Elite and show me a comparison table."*

Claude Code runs `convert_model` then `profile_workload` for each runtime and
renders the results.

---

## 5. Sample App 2 — MobileNetV2 on Arduino UNO Q

Run the **same** MobileNetV2 model on an Arduino UNO Q (QCS2210) board attached
over USB. This uses `samples/mobilenetv2/run_target_cpu.py`.

### Build & run

```powershell
# Prereq: adb on PATH, one device listed
adb devices

cd samples\mobilenetv2
.venv\Scripts\python.exe run_target_cpu.py
```

The orchestrator preprocesses the host image into a float32 NCHW `.npy`, pushes
the model + input + labels + `deploy/inference.py` to `/data/local/tmp/quad/`
on the board, runs inference over `adb shell`, and prints latency + top-K
predictions.

### Hardware reality on this SoC

On the shipped UNO Q Debian image, the Hexagon DSP and Adreno GPU are **not**
reachable by the SNPE/QNN runtime (no `/dev/fastrpc*`; OpenCL is Mesa rusticl,
not the Adreno driver). The **working on-target path is ONNX Runtime CPU**,
which is what `deploy/inference.py` uses. This is an honest limitation of this
board variant — the NPU silicon exists but the compute stack isn't exposed.

> Use UNO Q to validate the **portability** of your pipeline to an edge SoC;
> use the Snapdragon X Elite to demonstrate **NPU acceleration**.

---

## 6. Profiling results & how to read them

These are **real measured numbers** from the QUAD `mobilenetv2` sample.

### Snapdragon X Elite — CPU vs NPU

| Metric | CPU (ONNX Runtime) | NPU (QNN HTP) |
|--------|--------------------|---------------|
| Avg latency | 6.4 ms | **5.48 ms** |
| Throughput | 157 FPS | **183 FPS** |
| Speedup | 1.0× | **1.2×** |
| Avg CPU utilisation | 47% | ~0% (offloaded) |
| Est. package power | ~10.7 W | **~4.5 W** |

**Reading it:** the NPU is modestly faster *and* uses **less than half the
power** while freeing the CPU entirely — the headline win on a battery device
is energy efficiency, not just raw latency.

### Arduino UNO Q — ONNX Runtime CPU (Cortex-A53 quad-core)

| Metric | Value |
|--------|-------|
| Avg latency | ~64 ms |
| P50 latency | ~62 ms |
| P99 latency | ~71 ms |
| Throughput | ~15–16 FPS |
| Model | mobilenetv2.onnx (FP32) |

**Reading it:** ~10× slower than the X Elite CPU — expected for a low-power
edge SoC running FP32 on four A53 cores. INT8 quantization is the first lever
to pull here.

---

## 7. Optimization recommendations

Based on the profiles above, in priority order:

1. **Offload to the NPU (Hexagon HTP) on Snapdragon X Elite.**
   Best latency *and* lowest power (~4.5 W vs ~10.7 W). For any sustained or
   battery-sensitive workload, this is the default choice.

2. **Quantize to INT8 with calibration data.**
   MobileNetV2 quantizes cleanly. Pass `--calibration <dir>` with ~50–100
   representative images so INT8 accuracy stays close to FP32. On UNO Q, INT8
   on the A53 CPU is the single biggest speed lever available.

3. **Use the right power mode for the job (`orchestrate_workload`).**
   - **Performance** — lowest latency, highest power. Bursty / interactive use.
   - **Balanced** — good latency/power trade-off. The sensible default.
   - **Efficiency** — lowest power, slightly higher latency. Always-on / streaming.
   Compare them with `/quad-orchestrate` before committing.

4. **Benchmark with `--duration`, not per-call timing.**
   Process-spawn overhead (~1 s) dominates single-shot calls and makes the NPU
   look slow. The sample's `qnn-net-run --duration 10s` runs 1000+ iterations in
   one process for accurate averages — do the same in your own apps.

5. **Pick the backend per model, not per device.**
   Small CNNs like MobileNetV2 see modest NPU speedups (compute-light, the CPU
   keeps up); larger models (transformers, detectors) show much bigger NPU wins.
   Always profile *your* model — use `profile_workload` on each runtime and let
   the numbers decide.

6. **GPU (Adreno) as the middle ground.**
   When the NPU is busy or an op is unsupported on HTP, route to the Adreno GPU
   via `libQnnGpu` (see the GPU Inference sample) rather than falling back to CPU.

> In Claude Code you can simply ask: *"Given these profiles, what's the best
> backend and power mode for a battery-powered always-on camera?"* — the
> `/quad-recommend` skill synthesises model + target + use case into a concrete
> recommendation.

---

## 8. Two more simple sample apps

### A. GPU Inference (`samples/gpu_inference/`)

End-to-end targeting of the **Adreno GPU** via QUAD: detect hardware, convert an
ONNX model, profile with `runtime="gpu"`, and generate C++ inference code using
`libQnnGpu`.

```powershell
cd samples\gpu_inference
.\run.ps1
.venv\Scripts\python.exe gpu_inference.py
# Or a custom model:
.venv\Scripts\python.exe gpu_inference.py --model path\to\model.onnx
```

Mock mode works for development; real GPU execution needs a Snapdragon device
with an Adreno GPU + QAIRT SDK.

### B. Whisper Streaming ASR (`samples/whisper_asr/`)

Real-time speech-to-text using **Whisper-tiny** with an **NPU-accelerated
encoder** and **CPU decoder** — a nice example of multi-backend orchestration.

```
Microphone/WAV → 80 ms chunks → 5 s sliding window → Mel spectrogram (CPU)
    → Encoder (NPU INT8) → Decoder (CPU INT8) → Streaming text → Console
```

```powershell
cd samples\whisper_asr
.\run.ps1
.venv\Scripts\python.exe whisper_asr.py            # live mic
.venv\Scripts\python.exe whisper_asr.py --wav sample.wav
```

This shows the QUAD pattern applied to a **pipeline**: the mel frontend and
decoder run on CPU while the heavy encoder is offloaded to the NPU — exactly the
kind of split `orchestrate_workload` helps you reason about.

---

## 9. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: fastmcp` | Run `.\run.ps1` in the sample directory |
| `Could not find a Python that can import quad.mcp.server` | Install the QUAD server: `cd ..\..\QUAD && .\install.ps1` |
| `qairt-converter not found` | Install the QAIRT SDK: `.\install.ps1 -QairtArchive <path>` |
| `NPU benchmark skipped: QNN_SDK_ROOT not set` | Run `.\install.ps1` in the QUAD-Client root to create `.QUAD/` paths |
| `DspTransport.openSession failed` | HTP init warning only — the graph still compiles and runs on the NPU |
| Low / random predictions | Use `--calibration` with representative images for INT8 accuracy |
| UNO Q: `QNN_COMMON_ERROR_PLATFORM_NOT_SUPPORTED` | Expected on this board — use the ONNX Runtime CPU path (default) |

---

*Generated for the QUAD Client SDK. Every sample lives under `samples/` and
follows the standard `run.ps1` + `requirements.txt` convention.*
