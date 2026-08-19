# AURA

**Autonomous Understanding & Responsive Agent**

### On-Device Intelligence with AURA: Autonomous Understanding and Responsive Agents on Qualcomm Platforms

> *An AI Agent for the Physical World.*
>
> **Eyes. Ears. Memory. Intelligence. Action.**

AURA is a **privacy-first Physical-AI agent** for the **Arduino VENTUNO Q** and
Qualcomm **IQ8 / QCS8275** reference target. It acts as your eyes, ears, memory,
and intelligence in the real world. Perception, speech processing, semantic
memory, and the default reasoning path run locally with no cloud dependency.

For a higher-quality development configuration, AURA can optionally use a
Qwen3-4B Genie endpoint running on a trusted Snapdragon host over an SSH tunnel.
This remains a local-network hybrid mode: sensor data and memory stay on IQ8,
and only the grounded reasoning request is sent to the trusted local endpoint.

AURA can:

- 👁️ **See** through cameras
- 👂 **Hear** through microphones
- 🧠 **Understand and reason** using local LLMs
- 📚 **Remember** events and conversations
- 🗣️ **Communicate** naturally via voice
- 🤖 **Act** through IoT devices, robots, and actuators
- 🔒 **Keep sensor data local** — hybrid mode sends only selected grounded context to a trusted host

The VENTUNO Q's dual-brain architecture (AI inference + real-time control)
makes it well suited for agents that **perceive, decide, and act** in the
physical world.

> **Status: v0.1.** Structure, docs, and the core `Event` contract are in place.
> **Milestones 1 (Eyes), 2 (Ears/Voice), 3 (Memory), and 4 (Brain) are
> implemented** — YOLOv8 detection and Whisper STT / piper TTS feeding a SQLite
> event log with object last-seen lookup and query/recall, plus a local
> OpenAI-compatible LLM client that summarizes and answers grounded in
> remembered Events (see `examples/`). Milestones 1–2 are **verified on the IQ8**
> (vision on the Hexagon NPU) — see [`docs/IQ8_DEPLOYMENT.md`](docs/IQ8_DEPLOYMENT.md).
> Milestone 5 (Action) ships as importable stubs. See [`docs/ROADMAP.md`](docs/ROADMAP.md).
>
> The target IQ8 multimodal profile is YOLOv8n Detection for vision, YAMNet plus
> Whisper Base/Small for audio, All-MiniLM-L6-v2 for semantic memory, and a
> Qwen3-4B-Instruct-2507 W4A16 reasoning endpoint. The perception and memory
> models support IQ8 deployment. The Qwen3 W4A16 bundle is currently used from a
> supported local Genie/GenieX host because IQ8 is not an officially listed
> target for that bundle.

---

## Quick Start

```bash
git clone <your-fork-url> AURA && cd AURA

# base install (light — numpy + pydantic only) and dev tooling
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# sanity check: everything imports, Event round-trips
pytest -q

# inspect resolved configuration
aura config
```

Enable a milestone's dependencies as you work on it:

```bash
pip install -e ".[vision]"   # 👁️  Milestone 1 (camera + YOLO ONNX)
pip install -e ".[speech]"   # 👂🗣️  Milestone 2 (Whisper + TTS)
pip install -e ".[memory]"   # 📚  Milestone 3 (vector recall)
pip install -e ".[agent]"    # 🧠🤖  Milestone 4/5 (local LLM + tools)
pip install -e ".[dashboard]"# 🖥️  FastAPI + Streamlit UI
```

---

## How It Works

A **perceive → remember → reason → act** loop. Perception and memory remain on
IQ8; reasoning can use either the on-device CPU fallback or the optional trusted
local Qwen3 Genie endpoint:

```
 Camera ─▶ YOLOv8n Detection ──────────────┐
                                           │
 Mic ─▶ YAMNet ─▶ speech/audio trigger ────┼─▶ Events ─▶ MiniLM-v2 ─▶ SQLite
                    └─▶ Whisper Base/Small ┘              embeddings     memory
                                                                            │
                                                                            ▼
                                                          retrieve relevant Events
                                                                            │
                                                                            ▼
                                                Local CPU LLM or Qwen3 Genie endpoint
                                                                            │
                                                                            ▼
                                                               answer / TTS / action
```

Everything flows through one small data contract, `aura.core.events.Event`, so
each capability can be built and tested independently. Full diagram and the
Event schema: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## IQ8 Multimodal Reference Stack

| Capability | Model | IQ8 execution | Role |
|---|---|---|---|
| Eyes | YOLOv8n Detection | QNN / Hexagon NPU | Detect objects from camera frames and produce scene Events. |
| Ears — events | YAMNet | QNN / Hexagon NPU | Continuously classify environmental audio and gate expensive speech recognition. |
| Ears — speech | Whisper Base | QNN / Hexagon NPU or existing `whisper.cpp` path | Default speech-to-text model for interactive latency. |
| Ears — accurate speech | Whisper Small | QNN / Hexagon NPU, on demand | Optional higher-accuracy transcription when latency permits. |
| Memory | All-MiniLM-L6-v2 | QNN / Hexagon NPU | Generate 384-dimensional embeddings for semantic recall. |
| Brain | Qwen3-4B-Instruct-2507 W4A16 | Genie/GenieX on a supported trusted local host | Reason over retrieved Events through an OpenAI-compatible endpoint. |
| Brain fallback | Qwen2.5 0.5B GGUF | `llama.cpp` on IQ8 CPU | Fully standalone reasoning when the host Genie endpoint is unavailable. |

The recommended audio path runs YAMNet continuously and invokes Whisper only
when speech or another configured event is detected. This reduces unnecessary
Whisper inference and leaves NPU capacity available for vision and memory.

Semantic memory stores Events and MiniLM embeddings in SQLite. Retrieval embeds
the current question, ranks stored vectors by cosine similarity, and supplies
the top matching Events as grounding context to the LLM. A direct SQLite vector
store is preferred on IQ8 over a heavier always-running vector database.

### Brain Operating Modes

**Standalone IQ8 mode**

```text
IQ8 perception + MiniLM memory → IQ8 llama.cpp CPU endpoint on 127.0.0.1:8080
```

**Hybrid local-development mode**

```text
IQ8 perception + MiniLM memory
    → IQ8 127.0.0.1:18081
    → SSH reverse tunnel
    → trusted Snapdragon host 127.0.0.1:8081
    → Qwen3-4B-Instruct-2507 W4A16 Genie endpoint
```

Keep both model endpoints loopback-only. Do not expose the OpenAI-compatible
ports directly to the office network. The hybrid mode should transmit only the
question and retrieved grounding Events, not raw camera frames, audio, or the
complete memory database.

### Model References

- [YOLOv8 Detection — Qualcomm AI Hub](https://aihub.qualcomm.com/models/yolov8_det)
- [YAMNet — Qualcomm AI Hub](https://aihub.qualcomm.com/models/yamnet)
- [Whisper Base — Qualcomm AI Hub](https://aihub.qualcomm.com/models/whisper_base)
- [Whisper Small — Qualcomm AI Hub](https://aihub.qualcomm.com/models/whisper_small)
- [All-MiniLM-L6-v2 — Qualcomm AI Hub](https://aihub.qualcomm.com/models/minilm_l6_v2)
- [Qwen3-4B-Instruct-2507 — Qualcomm AI Hub](https://aihub.qualcomm.com/models/qwen3_4b_instruct_2507)

---

## Project Layout

```
AURA/
├── src/aura/
│   ├── core/         # Event contract + AuraPipeline (perceive→remember→reason→act)
│   ├── vision/       # 👁️  cameras + YOLO/VLM → Events        (Milestone 1)
│   ├── speech/       # 👂🗣️  Whisper STT + piper TTS            (Milestone 2)
│   ├── memory/       # 📚  SQLite + vector recall              (Milestone 3)
│   ├── agent/        # 🧠🤖  local LLM + actuator tools        (Milestone 4/5)
│   ├── dashboard/    # 🖥️  FastAPI + Streamlit UI
│   ├── config.py     # AURA_* settings (env / .env)
│   └── cli.py        # `aura` command-line entry point
├── deploy/iq8/       # on-device drivers (NPU vision + speech) for the IQ8
├── docs/             # ARCHITECTURE.md · ROADMAP.md · NPU_SETUP.md · IQ8_DEPLOYMENT.md
├── examples/         # runnable demos (added per milestone)
├── scripts/          # run_dashboard.sh · run_device.sh
├── tests/            # smoke tests (imports + Event round-trip)
├── pyproject.toml    # packaging (hatchling) + optional-dependency groups
├── requirements.txt  # light base deps
└── .env.example      # config template (copy to .env — never commit secrets)
```

---

## Milestones

| # | Name        | Capability                                            | Status |
|---|-------------|-------------------------------------------------------|:------:|
| 1 | 👁️ Eyes     | camera → YOLO detection → scene Events                | ✅ |
| 2 | 👂🗣️ Ears     | mic → Whisper STT · piper voice replies               | ✅ |
| 3 | 📚 Memory   | store events/objects · time + semantic queries        | ✅ |
| 4 | 🧠 Brain    | local LLM summaries, reasoning, grounded answers      | ✅ |
| 5 | 🤖 Action   | control lights, relays, smart devices, mobile robot   | ⬜ |

Details, outputs, and definitions-of-done: [`docs/ROADMAP.md`](docs/ROADMAP.md).
Milestones 1–2 are **verified on the IQ8** (vision on the Hexagon NPU; speech
via whisper.cpp + piper) — see [`docs/IQ8_DEPLOYMENT.md`](docs/IQ8_DEPLOYMENT.md).

---

## Software Stack

| Layer     | Choice                                              |
|-----------|-----------------------------------------------------|
| OS        | Ubuntu Linux on VENTUNO Q                           |
| Languages | Python, C/C++                                        |
| Vision    | YOLOv8n Detection via QNN NPU; ONNX fallback         |
| Audio     | YAMNet event detection via QNN NPU                   |
| Speech    | Whisper Base/Small STT; piper/MeloTTS output          |
| Memory    | SQLite + All-MiniLM-L6-v2 semantic embeddings        |
| LLM       | IQ8 llama.cpp CPU fallback or trusted-host Qwen3 Genie endpoint |
| Agent     | LangGraph · MCP-compatible tools (future phase)     |
| Storage   | SQLite event log + lightweight vector retrieval      |
| UI        | FastAPI + Streamlit                                 |

> **Qualcomm acceleration:** YOLOv8n, YAMNet, Whisper, and MiniLM target the IQ8
> Hexagon NPU through QNN. The requested Qwen3-4B-Instruct-2507 W4A16 bundle is
> not currently an officially listed IQ8 target, so use `aura.agent.genie_server`
> on a supported trusted local host or the IQ8 CPU fallback. See
> [`docs/NPU_SETUP.md`](docs/NPU_SETUP.md).

---

## Demo Scenario

> User leaves the room. The camera records events. AURA stores observations.
> The user returns and asks: **"What happened while I was gone?"**
>
> AURA responds: *"Two people entered the room, a package was delivered, and the
> lights were switched off at 4:15 PM."*

A showcase of the VENTUNO Q vision — bringing AI from the cloud into the
physical world through **local** perception, reasoning, memory, and action.

---

## Contributing

Pick a milestone from [`docs/ROADMAP.md`](docs/ROADMAP.md), install its extra,
and replace the `NotImplementedError` stubs. Keep heavy imports lazy (inside
methods) so the base package stays importable on-device. Run `pytest -q` and
`ruff check` before opening a PR.

## License

Apache-2.0 — see [`LICENSE`](LICENSE).
