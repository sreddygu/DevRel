# LLM (UNOQ): GGUF + llama.cpp

Run small, CPU-friendly LLMs on Arduino UNOQ (Linux side) using `llama.cpp` and GGUF models.

## What’s Here

- Notebook (setup + inference): `llm_gguf_llamacpp.ipynb`
- CLI helper (runs `llama-cli` / `llama-server`): `run_llama_cpp.py`

## Recommended Models (UNOQ)

- TinyLlama `1.1B` (GGUF, `Q4_K_M` or similar)
- Qwen2/Qwen2.5 `0.5B` (GGUF, `Q4_K_M`)
- Phi-2 `2.7B` is borderline (aggressive quantization + short context)

Avoid: 7B+ models and any VLMs (won’t fit / too slow).

## Larger Models (IQ9, not UNOQ)

The IQ9 has the memory/compute headroom for bigger models. Default wired up here:

- Gemma 4 `12B` (instruction-tuned, QAT `q4_0` GGUF): `models/gemma-4-12b-it-qat-q4_0.gguf` (~7 GB)
  - Source: https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf (ungated)
  - For image input, also fetch `mmproj-gemma-4-12b-it-qat-q4_0.gguf` and pass it via `--extra "--mmproj models/mmproj-gemma-4-12b-it-qat-q4_0.gguf"`.

This model is **too large for the UNOQ** — run it on the IQ9.

## Setup (UNOQ)

- Install build tools (once): `sudo apt-get install -y build-essential cmake git`
- Build `llama.cpp`:
  - `git clone https://github.com/ggerganov/llama.cpp`
  - `cd llama.cpp && cmake -S . -B build && cmake --build build -j`
- Put a GGUF model somewhere on UNOQ (example):
  - `~/qa-intermediate-curriculum/projects/LLM/models/<model>.gguf`

## Run (UNOQ)

- Direct:
  - `./llama.cpp/build/bin/llama-cli -m models/<model>.gguf -p "Say hello" -n 64 --ctx 512`
- Via helper:
  - `python3 run_llama_cpp.py --llama-cpp-dir ~/llama.cpp --model models/<model>.gguf --prompt "Say hello" --n-predict 64 --ctx 512`

## Training (practical note)

UNOQ is for inference. If you need “training”, do it on a PC (LoRA/QLoRA), then convert/quantize to GGUF for UNOQ.

