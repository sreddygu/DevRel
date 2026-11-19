# Qwen3-14B on the llama.cpp Hexagon (HTP/NPU) backend

Goal: run **Qwen3-14B (Q4_0 GGUF)** on the Qualcomm **Hexagon NPU** via llama.cpp's
experimental `ggml-hexagon` backend — *not* the QNN→Genie pipeline (that path needs
original weights + an x86_64 host and is documented separately in `CLAUDE.md`).

    Qwen3-14B Q4_0 GGUF
          ↓
    llama.cpp  (built with GGML_HEXAGON=ON)
          ↓
    libggml-htp-v81.so / v75  (HTP session runtime)
          ↓
    HTP (NPU)   — IQ9 = v81, IQ8 = v75

## Why 14B (and not 32B)

The backend runs the NPU as sessions of **2048 MB each, HTP0–HTP4 (5 max)**. Per the
llama.cpp Snapdragon docs: *"models under 4B fit one session; 8B needs two; 20B needs
four."* So the ceiling is ~20B. **Qwen3-32B (~18 GB Q4_0) exceeds 5 sessions and will
not load.** Qwen3-14B needs ~3 sessions and fits. Start here; it is the honest largest
dense Qwen3 for this backend.

## Format matters: must be Q4_0

The Hexagon backend's supported/tested path is **Q4_0** weights (KV cache q8_0). The
`Q4_K_M` GGUF already in `models/` will likely NOT run on HTP — fetch the **Q4_0** build:

    huggingface-cli download Qwen/Qwen3-14B-GGUF Qwen3-14B-Q4_0.gguf \
      --local-dir C:/llm_hexagon/models
    # (verify the exact repo/filename on HF; use the Q4_0 asset, not Q4_K_M/MXFP4)

## Run from PLAIN DISK, never Dropbox

llama.cpp mmaps the GGUF. Under `C:\Dropbox\...` mmap is blocked (same failure that
breaks Genie bundles — see the vault memory note). Copy/download the model and the
built binaries to a non-synced path, e.g. **`C:\llm_hexagon\`**, and run from there.

## Prerequisites (as of 2026-08-19 — GAPS on this host)

Native Windows-on-Snapdragon (ARM64) build needs:

- [x] Hexagon compiler — `C:\Qualcomm\HEXAGON_Tools\19.0.07`
- [x] QAIRT 2.47.1 — `C:\Qualcomm\AIStack\QAIRT\2.47.1.260610`
- [ ] **Hexagon SDK 6.6+** — NOT installed (only the standalone compiler is). Needed for
      FastRPC stubs. Install via Qualcomm Package Manager (QPM).
- [ ] **OpenCL SDK 2.3+** — NOT found. Needed for the Adreno/`GGML_OPENCL` half.
- [ ] **CMake** — not on PATH. Install (winget: `Kitware.CMake`) or add to PATH.
- [x] VS 2026 / LLVM-Clang ARM64 toolchain — `clangarm64` present on PATH.

## Build (once prerequisites are met)

From a fresh llama.cpp checkout (the existing `llama.cpp-win-arm64/` is CPU-only —
no `libggml-htp-*`, so it must be rebuilt):

    git clone https://github.com/ggml-org/llama.cpp
    cd llama.cpp
    # copy the snapdragon CMake preset per docs/backend/snapdragon, then:
    cmake --preset arm64-windows-snapdragon-release -B build-snapdragon \
      -DGGML_HEXAGON=ON -DGGML_OPENCL=ON -DGGML_OPENMP=OFF
    cmake --build build-snapdragon
    cmake --install build-snapdragon --prefix C:/llm_hexagon/llama.cpp

This produces `libggml-htp-v73/v75/v79/v81.so` alongside the binaries.

## Run

The NPU appears as a pseudo-GPU device `HTP0..HTP4`; offload with `-ngl`.

    # PC (X Elite, v75-class) or copy to device. Model on plain disk.
    llama-cli -m C:/llm_hexagon/models/Qwen3-14B-Q4_0.gguf \
      --device HTP0,HTP1,HTP2 -ngl 99 -c 4096 \
      -p "Explain the Hexagon NPU in one paragraph." -n 128

    # On IQ9 (v81) via adb/ssh, the doc's wrapper form:
    #   M=Qwen3-14B-Q4_0.gguf D=HTP0,HTP1,HTP2 ./scripts/snapdragon/adb/run-completion.sh -p "..."

`GGML_HEXAGON_NDEV` controls session count; use 3 for 14B (`D=HTP0,HTP1,HTP2`).

## Status

- 2026-08-19: Scaffolded. Target set to Qwen3-14B Q4_0 (32B ruled out — exceeds session
  ceiling). Build blocked on missing Hexagon SDK 6.6+, OpenCL SDK, and cmake on this host.
  Backend itself is upstream-experimental.
