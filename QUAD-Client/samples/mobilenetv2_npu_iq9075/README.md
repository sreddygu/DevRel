# MobileNetV2 — CPU / NPU benchmark on Dragonwing IQ-9075 EVK

Runs MobileNetV2 on the IQ-9075 EVK (QCS9075) over **adb (USB) or ssh
(Wi-Fi/Ethernet)**: a real CPU benchmark, an honest NPU/GPU attempt via
the `onnxruntime-qnn` plugin EP (documented as blocked on this board's
Linux device layout — not a script bug), and — when a pre-compiled QNN
context binary is supplied — a **genuine NPU inference pass via
`qnn-net-run`** with real, measured latency.

```
samples/mobilenetv2_npu_iq9075/
├── run_iq9075.py        — host-side orchestrator (adb or ssh transport; push + run + report)
├── deploy/inference.py  — on-device script: CPU (real), NPU/GPU plugin-EP (attempted, honest), NPU context-binary (real, when supplied)
├── mobilenetv2.onnx      — ONNX Model Zoo export (CPU / plugin-EP path)
├── test_input.jpg
├── requirements.txt
├── run.ps1               — uv-based dependency installer (host side)
└── tests/                 — unit + smoke + end-to-end tests
```

## Two independent NPU/GPU code paths — do not conflate them

| | `onnxruntime_qnn` plugin EP (default, no extra flags) | `qnn-net-run` + context binary (`--qnn-context-bin`) |
|---|---|---|
| Status | **Blocked, structurally, on this board** — `onnxruntime`'s Linux device-discovery code expects a DRM GPU node with a `vendor` file; this board's Hexagon NPU is exposed via `/dev/fastrpc-*` instead, which that code doesn't recognize. No newer `onnxruntime`/`onnxruntime-qnn` release fixes this. | **Works** — verified live, measured latency. Requires the board's on-device QAIRT version to be ≥ the version the binary was compiled for (`qnn-net-run --version`). |
| Verified latency | N/A (never active) | ~2.5–2.7 ms mean, ~325–350 FPS on Hexagon HTP v73 |

Full findings, environment pinning, and caveats:
[`docs/debugging/8. NPU_Profiling_MobileNetV2_IQ9075.md`](../../docs/debugging/8.%20NPU_Profiling_MobileNetV2_IQ9075.md)
(local source of truth — not committed to the public repo).

**Caveat carried over from that report:** the CPU path here profiles
the ONNX Model Zoo `mobilenetv2.onnx` export; the NPU context-binary
path profiles a *different* MobileNetV2 checkpoint (the AI Hub Models
catalog `mobilenet_v2`, supplied separately as a `.bin` — see below).
They are not directly comparable as a same-model CPU-vs-NPU number.

## Quick Start

### Over SSH (Wi-Fi/Ethernet)

```powershell
# One-time: install host-side dependencies
.\run.ps1

# CPU + onnxruntime_qnn plugin-EP attempt
.venv\Scripts\python.exe run_iq9075.py --transport ssh --host <board-ip>

# CPU + a genuine NPU pass via a pre-compiled context binary
.venv\Scripts\python.exe run_iq9075.py --transport ssh --host <board-ip> `
    --qnn-context-bin <path-to>\mobilenet_v2.bin
```

### Over adb (USB)

```powershell
.venv\Scripts\python.exe run_iq9075.py --transport adb `
    --qnn-context-bin <path-to>\mobilenet_v2.bin --qnn-backend-lib /usr/lib/libQnnHtp.so
```

**Windows/Git-Bash note:** if invoking from Git Bash rather than
PowerShell, MSYS's path conversion can mangle `/usr/lib/libQnnHtp.so`
into a garbled Windows path. Either set `MSYS_NO_PATHCONV=1` or double
the leading slash (`//usr/lib/libQnnHtp.so`).

## Getting a QNN context binary

This sample does not ship a `.bin` (binaries are gitignored — see
`.gitignore`'s `*.bin` rule; they're board/SDK-version-specific
build artifacts, not source). Obtain one via:
- `mcp__quad__convert_model` (target_sdk="qnn") through the QUAD MCP
  server — see `CLAUDE.md`'s MCP registry note if the tool is missing.
- Qualcomm AI Hub Models' cloud compiler directly, using
  `QAI_HUB_API_KEY` (see `.env.example`) as a fallback when the MCP
  tools are unavailable.

Check the binary's target QAIRT version in its exported `metadata.json`
against the board's `qnn-net-run --version` before trusting it —
AI Hub compiles for QAIRT ≥2.45; an older on-device QAIRT will reject
a newer binary with "Using newer context binary on old SDK."

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.10+ (host) | `python --version` |
| `adb` on PATH (adb transport) | `winget install Google.PlatformTools` |
| `ssh`/`scp` on PATH (ssh transport) | Windows OpenSSH Client optional feature, or Git Bash |
| Board reachable | `adb devices` (USB) or `ssh root@<ip>` (Wi-Fi) |
| onnxruntime on-device | `pip3 install onnxruntime onnxruntime-qnn` (works once the board has internet + writable rootfs) |

## How It Works

`run_iq9075.py` (host) supports two transports behind one `BoardTarget`
abstraction (`--transport adb|ssh`) and never pushes a directory over
either — only individual files (model, `.npy`, NHWC raw input, labels,
`deploy/inference.py`, and the optional context binary).

`deploy/inference.py` (on-device) always runs CPU first — a real
benchmark. It then attempts NPU (`htp`) and GPU (`gpu`) via the
`onnxruntime_qnn` plugin EP, reporting the exact blocker reason when
`get_ep_devices()` doesn't surface a matching device. When
`--qnn-context-bin` is passed through, it separately runs a genuine NPU
pass via `qnn-net-run --retrieve_context <bin> --backend <lib>
--input_list ...`, parsing real latency out of `qnn-profile-viewer`.
This is a completely separate code path with its own input contract:
NHWC float32, `[0,1]`-range (not the NCHW ImageNet-normalized tensor
the CPU/plugin-EP paths use) — `run_iq9075.py` preprocesses and pushes
both formats when `--qnn-context-bin` is given.
