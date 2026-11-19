# Falcon3 7B NPU bundle — build & benchmark handoff

**Goal:** run Falcon3 7B Instruct locally on the Snapdragon X-Elite Hexagon
NPU (via SAGE's in-process `npu` provider) and benchmark decode throughput.

## Where we are

| Piece | State |
|---|---|
| SAGE app review | ✅ NPU LLM path (`src/npu_llm.py`) + benchmark engine (`src/llm_benchmark.py`) already implemented |
| Runtime host (this X-Elite) | ✅ native arm64, `onnxruntime-genai 0.14.1`, genai `Config.append_provider` API matches `npu_llm` — bundle will load on **QNN (Hexagon)** with no code changes |
| AI Hub token | ✅ present in `~/.qai_hub/client.ini` |
| Model choice | ✅ **Falcon3 7B Instruct** (open — AI Hub Models token only, no HF token) |
| Benchmark harness | ✅ `benchmark_npu_llm.py` written + smoke-tested (reports real prefill/decode tok/s and the active EP) |
| **The bundle** | ❌ **not built** — local WSL build OOM-kills |

## Why the local build failed

The AI Hub Models exporter loads Falcon-7B in **fp32 (~28 GB)** before tracing it
to ONNX. This box has **32 GB RAM**; WSL was capped at 28 GB + 128 GB swap,
but the kernel OOM-kills the process when RAM fills faster than swap engages
(`SLUB: Unable to allocate memory`). Three clean attempts, same wall.

(Also discovered & fixed along the way: WSL Ubuntu 26.04 ships only Python
3.14 — too new for torch — so the build script provisions CPython 3.12 via
`uv`; and the Falcon extra's `onnxsim` needs `build-essential` + `cmake`.)

## What to do — build on a bigger host

On any **non-arm64 host with ≥64 GB RAM** (x86 Linux box, cloud VM, or a
beefier workstation — *not* a win-arm64 machine, torch has no wheel there):

```bash
export QAI_HUB_API_TOKEN=<your-aihub-token>
bash build_falcon_npu_bundle.sh          # ~10–40 min, ~5 GB
# bundle lands in $DST (default: the WSL path; override DST= on other hosts)
```

Then copy the produced folder to this X-Elite at:

```
C:\work\QUAD\QUAD-Deliverables\sewa-apps\SAGE\models\falcon-v3-7b-instruct\
```

(It must contain `genai_config.json`, the `*.onnx`/`rank_*.onnx` graph(s),
and `tokenizer.json`.)

## Then benchmark (here, on the X-Elite)

```bash
cd C:/work/QUAD/QUAD-Deliverables/sewa-apps/SAGE
.venv/Scripts/python.exe benchmark_npu_llm.py --model falcon-v3-7b-instruct
```

It prints the load time, the active execution provider (expect **QNN ←
Hexagon NPU**), and median decode tok/s across the sample prompts. You can
also benchmark it against Ollama/cloud side-by-side via the in-app
**Benchmark** tab (Settings → provider `npu`).

## Constrained-host alternative

If no ≥64 GB host is available, a smaller model exports within 32 GB
(`llama-3.2-3b-instruct`, fp32 ~6 GB) — but it's **gated** (needs an HF
token + accepting Meta's license). Swap the `SLUG`/`FRIENDLY` in the build
script and pass `--hf-token`.
