# MobileNetV2 — CPU vs GPU vs NPU Benchmark on Snapdragon X Elite

One script that downloads MobileNetV2, converts it via the DevRel MCP server,
and benchmarks CPU (onnxruntime) vs GPU (Adreno) vs NPU (QNN Hexagon HTP) on Snapdragon X Elite.

```
samples/mobilenetv2/
├── run_mobilenetv2.py  — download + convert + benchmark (all-in-one)
├── requirements.txt    — Python dependencies
├── run.ps1             — uv-based dependency installer
└── README.md           — this file
```

---

## Quick Start

```powershell
# One-time: install sample dependencies
.\run.ps1

# Run the full pipeline
.venv\Scripts\python.exe run_mobilenetv2.py --image cat.jpg
```

That's it. The script:

1. **Downloads** MobileNetV2 ONNX from the ONNX Model Zoo + ImageNet labels
2. **Converts** to QNN DLC via the DevRel MCP server (auto-spawned as a subprocess — no server to start)
3. **Benchmarks** CPU (10 timed runs) vs GPU (Adreno, `--duration` benchmark) vs NPU (single-process `--duration` benchmark with 1000+ iterations)
4. **Prints** a side-by-side comparison table with latency, throughput, and power estimates

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.10+ | `python --version` |
| DevRel server installed | Clone [DevRel](https://github.qualcomm.com/pavanr/DevRel) in sibling dir and run `install.ps1` |
| QAIRT SDK | Downloaded and installed via DevRel's `install.ps1 -QairtArchive` |
| `.DevRel/` directory | Created by `devrelAgent/install.ps1` — contains SDK symlink + qairt-venv |

The script auto-discovers the DevRel server and SDK via the `.DevRel/` directory.
No environment variables (`QNN_SDK_ROOT`, etc.) need to be set manually.

---

## How It Works

### No server to start

The script uses **stdio transport** to spawn the DevRel MCP server as a child
subprocess. It calls `convert_model` over the MCP protocol, gets the result,
and the server exits automatically. There is no long-running server.

```
run_mobilenetv2.py
  │
  ├─ Step 1: urllib → download ONNX model + labels
  │
  ├─ Step 2: fastmcp Client(StdioTransport) → spawns python -m devrel.mcp.server
  │           → calls convert_model tool → gets DLC path → server exits
  │
  └─ Step 3: qnn-net-run.exe --duration 10s → 1000+ NPU iterations in one process
             qnn-net-run.exe --backend libQnnGpu → GPU iterations
             onnxruntime → 10 CPU iterations
             → three-way comparison table
```

### Accurate NPU timing

The NPU benchmark uses `qnn-net-run --duration <N>s` to run many iterations
in a single process. This avoids the ~1 second process-spawn overhead that
would dominate per-call timing. The average latency is computed as
`duration_seconds * 1000 / num_iterations`.

---

## Expected Output

```
STEP 1 — Download model
  [skip] mobilenetv2.onnx already exists.

STEP 2 — Convert to INT8
  Server : C:\work\DevRel\DevRel\.venv\Scripts\python.exe -m devrel.mcp.server
  Conversion time   26.5 s

STEP 3 — CPU vs NPU Benchmark (Snapdragon X Elite)
  ── CPU (onnxruntime) ──────────────────────────────
  [CPU] timed (10 run(s))
    run  1:    5.8 ms   CPU   76%
    ...

  ── NPU (QNN HTP) ──────────────────────────────────
  Running qnn-net-run --duration 10s --perf_profile burst ...
  1826 iterations in 11.2s  (avg 5.48 ms, 183 FPS)

COMPARISON — CPU (onnxruntime) vs NPU (QNN HTP)

  Metric                             CPU (onnxruntime)           NPU (QNN HTP)
  ──────────────────────────────────────────────────────────────────────────────
  Avg latency                                   6.4 ms                 5.48 ms
  Throughput                                   157 FPS                 183 FPS
  Speedup                                         1.0×                    1.2×
  Iterations                                        10                    1826
  ──────────────────────────────────────────────────────────────────────────────
  Avg CPU util                                     47%         ~0% (offloaded)
  Est. pkg power                               ~10.7 W                  ~4.5 W

  Top-5 predictions (NPU):
    1. golden retriever                  52.3%
    2. Labrador retriever                33.1%
    ...
```

---

## CLI Options

```
python run_mobilenetv2.py [OPTIONS]

Options:
  --image PATH          Test image (JPEG/PNG). Auto-downloaded if not found.
  --skip-download       Skip model download if already exists
  --model PATH          ONNX model path (default: mobilenetv2.onnx)
  --output-dir DIR      Converted model output dir (default: output/)
  --server URL          DevRel server: 'stdio' (default) or HTTP/SSE URL
  --adapter-mode MODE   mock | real (default: real if SDK installed)
  --target-sdk SDK      qnn | snpe | qairt (default: qnn)
  --warmup N            CPU warmup runs (default: 3)
  --runs N              CPU timed runs / NPU duration seconds (default: 10)
  --top-k N             Top-K predictions to show (default: 5)
  --calibration DIR     Calibration images for better INT8 accuracy
```

### Examples

```powershell
# Use your own photo
python run_mobilenetv2.py --image my_photo.jpg --skip-download

# Mock mode (no SDK needed — simulated conversion)
python run_mobilenetv2.py --adapter-mode mock

# Connect to a remote DevRel server
python run_mobilenetv2.py --server http://lab-machine:8080/sse

# SNPE DLC for Android/Linux
python run_mobilenetv2.py --target-sdk snpe
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: fastmcp` | Run `.\run.ps1` to install sample deps |
| `Could not find a Python that can import devrel.mcp.server` | Install DevRel server: `cd ..\..\..\DevRel && .\install.ps1` |
| `qairt-converter not found` | Install QAIRT SDK: `.\install.ps1 -QairtArchive <path>` |
| `DspTransport.openSession failed` | HTP init warning — graph still compiles and runs on NPU |
| `NPU benchmark skipped: QNN_SDK_ROOT not set` | Run `.\install.ps1` in devrelAgent root to create `.DevRel/` paths |
| Low accuracy / random predictions | Use `--calibration` with representative images for INT8 accuracy |

---

## Next Steps

- **Profile on NPU**: use `profile_workload` MCP tool for per-op latency breakdown
- **Multi-backend orchestration**: `orchestrate_workload` to split layers across CPU/GPU/NPU
- **Custom model**: swap `mobilenetv2.onnx` for any ONNX classifier; adjust `--model` path
- **INT4 quantization**: future — requires calibration data + AIMET adapter

---

## On Arduino UNO Q (QCM2290 / QRB2210) over USB

Run the same MobileNetV2 model on an Arduino UNO Q board attached via USB.

### Quick start

```powershell
# Prereq: adb on PATH (winget install Google.PlatformTools)
adb devices                                    # confirm one device listed

.venv\Scripts\python.exe run_target_cpu.py     # preprocess + push + run + report
```

The orchestrator preprocesses the host image into a float32 NCHW `.npy`,
pushes `mobilenetv2.onnx`, the input tensor, ImageNet labels, and
`deploy/inference.py` to `/data/local/tmp/devrel/` on the board, then
runs `python3 inference.py --json` over `adb shell` and prints latency
+ top-K predictions.

### Hardware reality on this SoC

The DevRel docs describe UNO Q as having a "Hexagon DSP V66 NPU,
1.0 TOPS, INT8" — that reflects the silicon, but on this Debian image
the SNPE/QNN runtime cannot reach it:

| Path | Status | Why |
|------|--------|-----|
| Hexagon DSP via SNPE/QNN | unavailable | No `/dev/fastrpc*`; the running `adsp` remoteproc serves audio (q6asm), not compute. SNPE 2.45 returns `QNN_COMMON_ERROR_PLATFORM_NOT_SUPPORTED`. |
| Adreno GPU via SNPE OpenCL | unavailable | OpenCL on board is Mesa **rusticl**, not Qualcomm's Adreno driver. SNPE GPU backend can't initialize. |
| QNN/SNPE CPU backend | unavailable | Same `QNN_COMMON_ERROR_PLATFORM_NOT_SUPPORTED`. |
| **ONNX Runtime CPU** | **works** | Python 3.13 + onnxruntime 1.26 ship in the Debian image. |

So the working on-target path on this UNO Q variant is **ONNX Runtime
CPU**, which is what `deploy/inference.py` uses.

### Measured KPIs (Cortex-A53 devrel-core, ORT CPU)

| Metric | Value |
|--------|-------|
| Avg latency | ~64 ms |
| P50 latency | ~62 ms |
| P99 latency | ~71 ms |
| Throughput | ~15-16 fps |
| Iterations | 20 timed (warmup 5) |
| Model | mobilenetv2.onnx (FP32) |

### CLI

```
python run_target_cpu.py [OPTIONS]

  --model PATH       ONNX model on host (default: mobilenetv2.onnx)
  --image PATH       Test image on host (default: test_input.jpg)
  --labels PATH      ImageNet class labels (default: imagenet_classes.txt;
                     auto-downloaded from PyTorch Hub if not present — the
                     labels are a public dataset artifact, not committed)
  --iterations N     Timed iterations (default: 10)
  --warmup N         Warmup runs (default: 3)
  --top-k N          Top-K predictions to show (default: 5)
  --skip-push        Reuse artifacts already at /data/local/tmp/devrel/
  --json             Emit raw JSON instead of formatted table
```

### Tests

```powershell
.venv\Scripts\python.exe -m pytest tests/ -q
```

The pytest suite covers preprocessing, label loading, top-K /
percentile / softmax math, JSON extraction from mixed stdout, adb
discovery (PATH + winget fallback), and device enumeration. All adb
calls are mocked; no board is required to run the suite.
