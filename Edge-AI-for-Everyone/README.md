# Edge AI for Everyone

### Theme: Build once, deploy anywhere

> *The same model, from your laptop to the smallest board.*
>
> **QAIRT · QNN · Genie · NPU — the on-device AI toolchain, end to end.**

Develop AI applications that run locally on Snapdragon platforms using **QAIRT,
QNN, GenieX, and NPU acceleration**. This is the **foundational / horizontal**
story — the toolchain and model-optimization workflow that every other story
depends on. It's where a developer learns the *pipeline*: take a model, quantize
it, target the NPU, and deploy the same artifact across the fleet.

> **Status: mostly built and verified.** This story is grounded in work already
> proven on the bench: Qwen3-4B W4A16 Genie export end-to-end (QAIRT 2.47), the
> IQ8/IQ9 CPU+NPU model matrix, and the LLM project's GGUF/llama.cpp path. The
> experimental **llama.cpp Hexagon (GGUF-direct NPU)** path is documented in
> `../LLM/HEXAGON_NPU.md`.

---

## Modules

| Module | What it does | Built on |
|---|---|---|
| **On-device LLMs** | Run a full LLM locally via Genie (NPU) or llama.cpp (CPU) | LLM + Agents projects |
| **Model optimization** | Right-size the model to the device's memory/compute | Agents E4B sizing notes |
| **Quantization** | W4A16 / Q4_0 / Q4_K_M — pick the format the runtime supports | Genie export · GGUF |
| **NPU deployment** | Convert → quantize → context-binary → Genie bundle → run on HTP | QAIRT converter pipeline |
| **RAG** | Ground answers in local documents via embeddings + retrieval | AURA memory (MiniLM + SQLite) |
| **Multimodal inference** | Vision + audio + text on the same device | AURA vision/speech |

---

## Device & Model Mapping

**Real, verified fleet matrix:**

| Device | SoC / HTP | CPU path | NPU path |
|---|---|---|---|
| **Snapdragon X Elite PC** | Hexagon v73 | Gemma-4-E4B Q4_K_M (llama.cpp) | Qwen3-4B-Instruct-2507 W4A16 (Genie) ✅ verified |
| **IQ8** | QCS8275 / Hexagon v75 (~11 GiB) | Qwen2.5-0.5B / E4B GGUF | v75 Genie — export pending; QNN vision (YOLO/MiniLM) ✅ |
| **IQ9** | QCS9075 / Hexagon v81 | Gemma-4-12B GGUF ✅ | Qwen3-4B Genie (reused bundle) |
| **Arduino UNO Q** | MCU + Linux | Tiny GGUF (0.5B) / ONNX | TinyML on-device |

**Quantization → runtime cheat-sheet:**

| Format | Runtime | Where it runs |
|---|---|---|
| **W4A16** | Genie / QAIRT | Hexagon NPU (context binaries) |
| **Q4_0** | llama.cpp + ggml-hexagon | Hexagon NPU (experimental, GGUF-direct) |
| **Q4_K_M** | llama.cpp | CPU |

> **The hard-won lesson (put this in front of developers):** *which processor
> actually runs the model* is decided by format + runtime support + whether the
> model fits the accelerator's memory — not by TOPS. A model in the wrong quant
> format silently falls back to CPU. See `../LLM/HEXAGON_NPU.md`.

---

## SDK / Software Stack

| Layer | Choice |
|---|---|
| NPU runtime | **QAIRT 2.47** · QNN · Genie / GenieX |
| CPU runtime | llama.cpp (GGUF), native ARM64 build |
| Conversion | qairt-converter → qairt-quantizer → qnn-context-binary-generator (x86_64 host) |
| Export helper | `qai-hub-models[...]` (AI Hub cloud export) |
| RAG | All-MiniLM-L6-v2 embeddings + SQLite retrieval |
| Serving | OpenAI-compatible endpoints (`genie_server.py`, llama-server) |

---

## Demo Scenario

> A developer clones the sample, runs `export` to produce a **W4A16 Qwen3-4B
> Genie bundle**, and serves it on the X Elite NPU. The **same** application code
> — only `--base-url` changes — then runs the CPU GGUF build on an IQ8. One app,
> two backends, zero cloud. They finish by adding RAG over a local PDF and asking
> a grounded question. **Model → NPU → answer, in one afternoon.**

---

## Where This Maps in the Repo

- **Core:** `../LLM` (GGUF + llama.cpp + `HEXAGON_NPU.md`) and `../Agents` (the
  portable agent + Genie/CPU backends + `agent_profiles.json` fleet matrix).
- **RAG/multimodal:** `../AURA` (memory + vision + speech).
- **MCP/remote:** `../QUAD-Client`.

## Event / Workshop Hooks

- **Flagship workshop (half day):** "Model to NPU to app" — export, quantize,
  deploy, serve, and swap backends across two devices.
- **Hackathon foundation:** this is the toolchain track every other story builds
  on; run it first at any multi-day event.
- **Content:** the *"It's not the TOPS"* explainer series (ties to the edge-AI
  developer-journey narrative).
