# XR-Powered Experiences

### Theme: Spatial AI for immersive interactions

> *An AI that sees what you see and understands where you are.*
>
> **Scene. Space. Voice. Reasoning — locally.**

Create intelligent XR companions that understand their surroundings, provide
contextual guidance, and interact naturally through multimodal experiences —
scene understanding, object recognition, and voice, all fused with a **local
LLM** so guidance is grounded in what the headset actually sees.

> **Status: narrative brief with a buildable proxy.** True XR needs **XR2-class
> silicon that is not on our bench** (flagged below). The *spatial-AI pipeline*
> — camera → detection → scene graph → grounded voice answer — is fully
> buildable **today on the IQ8/IQ9** using AURA's vision + speech + brain
> modules, and demoed on a monitor as a "headset-eye view." Port to real XR when
> hardware lands.

---

## Modules

| Module | What it does | Built on |
|---|---|---|
| **Spatial understanding** | Track camera pose / relative position of detected objects into a lightweight scene graph | AURA `vision/` + geometry |
| **Scene awareness** | Summarize "what's in front of me" as Events the LLM can reason over | AURA Events |
| **Object recognition** | Real-time detection of objects/surfaces in the field of view | YOLOv8n Detection (QNN NPU) |
| **Voice interaction** | Hands-free ask/answer — essential in XR | Whisper STT + piper TTS |
| **Local LLM inference** | Ground contextual guidance in the current scene, no cloud | Qwen3-4B Genie / GGUF fallback |

---

## Device & Model Mapping

**Real fleet (buildable proxy today):**

| Capability | Device / execution | Model |
|---|---|---|
| Object/scene vision | **IQ8** (QCS8275, Hexagon v75) or **IQ9** (v81) | YOLOv8n Detection — QNN / Hexagon NPU |
| Voice in/out | IQ8/IQ9 | Whisper Base (STT) · piper (TTS) |
| Spatial grounding memory | IQ8/IQ9 | All-MiniLM-L6-v2 embeddings → SQLite |
| Contextual reasoning | X Elite (v73) or IQ9 | Qwen3-4B-Instruct-2507 W4A16 (Genie) |

**Aspirational target silicon (NOT on bench — mark clearly in external use):**

| Platform | Target SoC | Why it matters | Status |
|---|---|---|---|
| Standalone XR headset | **Snapdragon XR2 Gen 2** | Dedicated XR compute + dual-display pipeline | Not in fleet |
| Smart glasses | **Snapdragon AR1 Gen 1** | Ultra-low-power always-on visual assist | Not in fleet |

> **Honest framing for decks:** we can demonstrate the *complete spatial-AI
> software stack* on IQ hardware as a first-person "what the headset sees" view.
> The XR2/AR1 line items are the intended production targets, not something we've
> run. Don't imply otherwise in customer-facing material.

---

## SDK / Software Stack

| Layer | Choice |
|---|---|
| Vision | YOLOv8n Detection via QNN NPU; ONNX Runtime fallback |
| Speech | Whisper Base/Small STT; piper/MeloTTS output |
| Spatial | Lightweight pose/scene-graph in Python (OpenCV geometry) |
| LLM | Qwen3-4B W4A16 via Genie (NPU) or GGUF via llama.cpp (CPU) |
| XR runtime (future) | OpenXR + Snapdragon Spaces (when XR2/AR1 hardware is available) |
| Acceleration | QAIRT 2.51 · QNN · Hexagon NPU |

---

## Demo Scenario

> A field technician wearing the headset (today: holding the IQ8 camera) looks at
> an unfamiliar equipment panel. *"What am I looking at, and what do I check
> first?"* AURA-XR recognizes the gauges and connectors in view, builds a scene
> summary, and the local LLM answers: *"That's the pump control panel — check the
> pressure gauge on the left; it should read 40–60 PSI."* **No cloud, no manual.**

---

## Where This Maps in the Repo

- Reuses **AURA** (`../AURA`) vision, speech, memory, and brain modules wholesale
  — XR is AURA with a spatial front-end and a head-worn camera.
- The `gesture_recognition` project (`../gesture_recognition`) is a natural input
  extension for hands-free XR control.

## Event / Workshop Hooks

- **Hackathon track:** "Point-and-ask" — build a first-person visual Q&A demo on
  an IQ device; best spatial grounding wins.
- **Workshop (2 hr):** wire YOLO scene detection → LLM guidance; run on the NPU.
- **Content:** demo video — *"Spatial AI without a headset: proving the XR stack
  on edge silicon first."*
