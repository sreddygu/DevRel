# FY27 DevRel Modular Developer Stories

Seven themed, **reusable** developer narratives for BU priorities, events,
workshops, hackathons, and content — as scoped in the FY27 DevRel Eng planning
discussions. Each story is a folder with a full README (theme, developer story,
module breakdown, device/model mapping, SDK stack, demo scenario, and
event/workshop hooks).

## The set

| # | Story | Theme | Folder | Status |
|---|---|---|---|:--|
| 1 | **Personal AI Companion (AURA)** | Privacy-first on-device AI | [`AURA/`](AURA/) | ✅ Built (M1–M4 verified on IQ8) |
| 2 | **AI Across Devices** | Seamless cross-device intelligence | [`AI-Across-Devices/`](AI-Across-Devices/) | 🟡 Buildable (2-node handoff) |
| 3 | **XR-Powered Experiences** | Spatial AI for immersive interaction | [`XR-Experiences/`](XR-Experiences/) | 🟡 Proxy on IQ; XR silicon aspirational |
| 4 | **Wearable AI Assistant** | AI that lives on your wrist | [`Wearable-AI/`](Wearable-AI/) | 🟡 Proxy on UNO Q; W5 aspirational |
| 5 | **Edge AI for Everyone** | Build once, deploy anywhere | [`Edge-AI-for-Everyone/`](Edge-AI-for-Everyone/) | ✅ Mostly built/verified |
| 6 | **Developer Journey** | First 30 min to first AI app | [`Developer-Journey/`](Developer-Journey/) | ✅ Buildable now |
| 7 | **Multiverse of Developers** | One platform, many personas | [`Multiverse-of-Developers/`](Multiverse-of-Developers/) | ✅ Routing/index brief |

> **Story 1 (AURA) is a pre-existing full project** — its README is the reference
> depth/format the other six follow. Stories 2–7 were authored as narrative
> briefs grounded in the same real fleet.

## Device & model coverage by story

Which devices and models each story exercises. **Bold** = the primary/verified
target; *italic* = aspirational silicon (not on bench). Each story's README has
the full mapping.

| # | Story | Primary devices | Aspirational | Reasoning model | Perception / other models | NPU runtime |
|---|---|---|---|---|---|:--:|
| 1 | Personal AI Companion (AURA) | **IQ8** · X Elite · IQ9 · VENTUNO Q | — | Qwen3-4B W4A16 (Genie) · Qwen2.5-0.5B / Gemma-4-E4B GGUF | YOLOv8n · YAMNet · Whisper · MiniLM | ✅ |
| 2 | AI Across Devices | **IQ8** (hub) · **X Elite** · **IQ9** | *Phone 8-series · W5 · XR2 Gen 2* | Qwen3-4B W4A16 (Genie) · Gemma-4-12B / Qwen2.5-0.5B GGUF | MiniLM (shared memory) | ✅ |
| 3 | XR-Powered Experiences | **IQ8** · **IQ9** · X Elite | *XR2 Gen 2 · AR1 Gen 1* | Qwen3-4B W4A16 (Genie) / GGUF | YOLOv8n · Whisper · MiniLM | ✅ |
| 4 | Wearable AI Assistant | **UNO Q** · **IQ8** (hub) | *Snapdragon W5+ Gen 1* | Qwen2.5-0.5B GGUF / Qwen3-4B (hybrid, hub) | `hey_dragon` KWS · gesture · sinewave · MiniLM | ✅ (hub) |
| 5 | Edge AI for Everyone | **X Elite** · **IQ8** · **IQ9** · UNO Q | — | Qwen3-4B W4A16 (Genie) · Gemma-4-E4B/12B · Qwen2.5-0.5B GGUF | MiniLM (RAG) · multimodal | ✅ |
| 6 | Developer Journey | **X Elite** → **IQ8** | — | Gemma-4-E4B GGUF (CPU) → Qwen3-4B W4A16 (Genie, stretch) | — | ✅ (stretch) |
| 7 | Multiverse of Developers | all: UNO Q · IQ8 · IQ9 · X Elite · VENTUNO Q | *routes to 2/3/4* | full palette (per persona) | full palette (per persona) | ✅ |

Quant format per runtime: **W4A16** → Genie/QAIRT (NPU) · **Q4_0** → llama.cpp
ggml-hexagon (NPU, experimental) · **Q4_K_M** → llama.cpp (CPU). See
[`Edge-AI-for-Everyone/README.md`](Edge-AI-for-Everyone/README.md) and
[`LLM/HEXAGON_NPU.md`](LLM/HEXAGON_NPU.md).

## How the stories relate

- **Story 5 (Edge AI for Everyone)** is the horizontal **toolchain** foundation —
  QAIRT/QNN/Genie/NPU. Every other story builds on it.
- **Story 6 (Developer Journey)** is the **onramp** — run it first at any event so
  everyone has a working setup.
- **Story 1 (AURA)** is the flagship **single-device** agent; **Story 2** extends
  it across devices; **Stories 3 & 4** re-skin it for XR and wearable form factors.
- **Story 7 (Multiverse)** is the **atlas** — it routes each developer persona to
  the right starting project above.

## Honest hardware grounding

All device/model tables are grounded in the **real bench fleet**:

| Device | SoC / HTP | Notes |
|---|---|---|
| Snapdragon X Elite PC | Hexagon v73 | Native ARM64; Qwen3-4B W4A16 Genie ✅ verified |
| IQ8 | QCS8275 / Hexagon v75 (~11 GiB) | QNN vision ✅; v75 Genie LLM export pending |
| IQ9 | QCS9075 / Hexagon v81 | Gemma-4-12B GGUF (CPU) ✅; roomier compute |
| Arduino UNO Q / VENTUNO Q | MCU + Linux | TinyML + dual-brain perceive/act |

Where a story implies silicon **not on the bench** (XR2 Gen 2, AR1, Snapdragon
W5), the README **flags it as aspirational** and maps the buildable demo to
hardware we actually have. Keep that distinction in any customer-facing deck.

## Reusable model palette

| Role | Model | Runtime |
|---|---|---|
| Vision | YOLOv8n Detection | QNN / Hexagon NPU |
| Audio events | YAMNet | QNN / Hexagon NPU |
| Speech | Whisper Base/Small | QNN NPU / whisper.cpp |
| Embeddings | All-MiniLM-L6-v2 | QNN NPU → SQLite |
| Reasoning (NPU) | Qwen3-4B-Instruct-2507 **W4A16** | Genie / QAIRT 2.47 |
| Reasoning (CPU) | Gemma-4-E4B / Gemma-4-12B / Qwen2.5-0.5B **GGUF** | llama.cpp |
| Wake / TinyML | `hey_dragon` KWS, gesture, sinewave | ONNX / TFLite Micro |
