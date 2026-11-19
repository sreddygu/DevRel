# CLAUDE.md — LLM project (Gemma 4 12B on Arduino IQ9)

Context for running Gemma 4 on the IQ9 edge device. Read this before resuming NPU work.

## Project layout

- `run_llama_cpp.py` — stdlib-only helper that shells out to `llama-cli`/`llama-server`. Default model is `models/gemma-4-12b-it-qat-q4_0.gguf`; default llama.cpp dir is `~/llama.cpp`.
- `llm_gguf_llamacpp.ipynb` — setup + inference notebook. `MODEL` cell points at the Gemma 4 GGUF.
- `models/` — GGUF files (git-ignored in practice; large). Holds the old `model.gguf` (396 MB, unused) plus the Gemma 4 files below.
- `README.md` — has a "Larger Models (IQ9, not UNOQ)" section documenting the Gemma 4 setup.

## The model

- **Gemma 4 12B** exists (released 2026-05-23, after the Jan-2026 knowledge cutoff — do not claim it doesn't exist).
- GGUF source (ungated): `https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf`
  - `gemma-4-12b-it-qat-q4_0.gguf` (~6.5 GB) — model
  - `mmproj-gemma-4-12b-it-qat-q4_0.gguf` (~168 MB) — vision projector (multimodal)
- The `...-unquantized` repo is BF16 safetensors (~24 GB), NOT GGUF — llama.cpp can't load it. Always use the `-gguf` repo for llama.cpp.

## CPU path (DONE, working)

Gemma 4 12B GGUF runs on the **IQ9 CPU** via llama.cpp. Verified end-to-end (~1.8 tok/s gen, aarch64 CPU-only build).

- Text: `cd ~/projects/LLM && python3 run_llama_cpp.py --prompt "..." --n-predict 128 --threads 8`
- Vision (uses mmproj, calls the multimodal CLI directly — `run_llama_cpp.py` only drives `llama-cli`):
  ```
  ~/llama.cpp/build/bin/llama-mtmd-cli -m models/gemma-4-12b-it-qat-q4_0.gguf \
    --mmproj models/mmproj-gemma-4-12b-it-qat-q4_0.gguf --image /path/img.jpg -p "Describe." -n 128 --threads 8
  ```
- Server: `python3 run_llama_cpp.py --server --host 0.0.0.0 --port 8080`

## NPU paths — TWO distinct options

There are two separate, mutually exclusive ways onto the Hexagon NPU. Do not mix them.

- **Path A — QNN → Genie** (below): original PyTorch/ONNX weights → `qairt-converter` →
  `qairt-quantizer` → `qnn-context-binary-generator` → Genie bundle → `genie-t2t-run`.
  GGUF CANNOT feed this. Needs an x86_64 host for the converters. Proven for Qwen3-4B
  (see `genie_bundle/`).
- **Path B — llama.cpp Hexagon backend**: **Q4_0 GGUF** → llama.cpp built with
  `GGML_HEXAGON=ON` → `libggml-htp-v*.so` → HTP. No converter, no Genie. Experimental.
  Target = **Qwen3-14B Q4_0** (32B exceeds the 5-session ceiling). See **`HEXAGON_NPU.md`**.

Either way: run from **plain disk, never `C:\Dropbox`** (mmap is blocked there).

### Path A details (IN PROGRESS — blocked on x86 host as of 2026-06-10)

Goal: run Gemma on the **Hexagon NPU** instead of CPU. GGUF CANNOT run on the NPU — it's a different format/runtime entirely. Required pipeline: original PyTorch/ONNX weights → `qairt-converter` → `qairt-quantizer` → `qnn-context-binary-generator` → Genie bundle → run on device.

### IQ9 device facts (verified)
- SoC: **Qualcomm QCS9075** (sa8775p family), NPU = **Hexagon HTP v81**.
- fastrpc/cDSP nodes live: `/dev/fastrpc-cdsp*`.
- **QAIRT 2.46 SDK** installed at `~/qairt_2.46.0.260424/qairt/2.46.0.260424` (on the device).
- Native aarch64-linux **`genie-t2t-run` IS present** (`bin/aarch64-oe-linux-gcc11.2/`) + `libGenie.so` — so the on-device runtime to RUN a converted model exists.

### The blocker
- The converter/quantizer tools (`qairt-converter`, `qairt-quantizer`, `qnn-onnx-converter`, `qnn-pytorch-converter`, `qnn-genai-transformer-composer`) ship **ONLY as `x86_64-linux-clang` binaries**. aarch64 dirs have only runtime tools (`qnn-context-binary-generator`, `qnn-net-run`, `genie-*`).
- The IQ9, the user's "Arm64 PC", and the WSL box (this machine — `aarch64`!) are ALL aarch64. None can run the converters.
- **User is procuring an x86_64 Linux machine** to do the conversion. Resume when available.

### When x86 host is ready
1. Install QAIRT **2.46.0.260424** (match device) + AIMET on the x86 box. Check Qualcomm AI Hub / Package Manager login (some components gated).
2. Pull Gemma's **original weights** (not GGUF) from HF.
3. Run convert → quantize → context-binary (target **HTP v81**) → assemble Genie bundle.
4. Deploy bundle to IQ9, run with the aarch64 `genie-t2t-run`.

### IMPORTANT caveats / honesty notes
- **User insists on 12B for the NPU.** Strongly recommend proving the path with a **2B–4B Gemma FIRST** — 12B is at/over the edge of HTP v81 memory; real risk it won't fit/compile. Validated Qualcomm on-device Gemma exports skew ≈2B. Don't grind on 12B before the pipeline is proven on a small model.
- **Alternative (no x86 needed):** Qualcomm AI Hub pre-compiled QNN bundle for a small Gemma → run via on-device `genie-t2t-run`. Sidesteps conversion entirely but won't be 12B.

## SSH access to IQ9 (from WSL)

- Host `192.168.29.185`, user `ubuntu`, password `qualcomm12349`. aarch64, 8 cores, 34 GB RAM.
- No `sshpass`/`sudo` on WSL. Used an askpass helper: `/tmp/askpass.sh` (echoes the password) with `SSH_ASKPASS_REQUIRE=force setsid -w ssh ...`. **Note: password is in plaintext at /tmp/askpass.sh — delete when done; SSH keys would be better.**
- Project on device: `~/projects/LLM`. llama.cpp at `~/projects/llama.cpp` (built, v9588), symlinked to `~/llama.cpp`.

## Cleanup TODO

- `/tmp/askpass.sh` on WSL holds the device password in plaintext — remove when finished.
- Old `models/model.gguf` (396 MB) on both WSL and IQ9 is unused — safe to delete.
