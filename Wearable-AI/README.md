# Wearable AI Assistant

### Theme: AI that lives on your wrist

> *Proactive, private, and always with you.*
>
> **Sense. Understand. Nudge — before you ask.**

Deliver proactive, privacy-preserving experiences using sensor data, health
signals, and personal context. Where [AURA](../AURA/README.md) reacts to what it sees and
hears, the wearable story is about **always-on, low-power sensing** and
**proactive** insight — the assistant surfaces something useful *before* the
user asks, and every signal stays on-device.

> **Status: proxy implemented on the IQ8** (see [Run the proxy](#run-the-proxy)); the brief below is unchanged.
> Original status: narrative brief with a buildable proxy. Production wearables need
> **Snapdragon W5-class silicon that is not on our bench** (flagged below). The
> **sensor-fusion + on-device inference loop** is buildable today on the
> **Arduino UNO Q / VENTUNO Q** (its MCU + sensors) and the existing TinyML
> projects (`wake_word`, `gesture_recognition`, `sinewave`), which are already
> sized for microcontroller-class targets.

---

## Modules

| Module | What it does | Built on |
|---|---|---|
| **Sensor fusion** | Combine IMU / motion / audio / (simulated) health streams into activity context | UNO Q sensors + `sinewave`/`gesture_recognition` |
| **Context awareness** | Infer state — walking, resting, meeting, anomaly — from fused signals | TinyML classifier on-device |
| **Health insights** | Trend detection over vitals (HR/steps/sleep proxies) with on-device thresholds | Lightweight on-device models |
| **Personal memory** | A compact rolling profile of routines/preferences, never uploaded | AURA `memory/` (trimmed) |
| **Low-power AI** | Keyword-spot / tiny-classifier gating so the big model wakes rarely | `wake_word` (`hey_dragon` KWS) |

---

## Device & Model Mapping

**Real fleet (buildable proxy today):**

| Capability | Device / execution | Model |
|---|---|---|
| Always-on wake | **Arduino UNO Q** (MCU) | `hey_dragon` streaming KWS (ONNX, tiny) |
| Motion/gesture | UNO Q / VENTUNO Q | `gesture_recognition` classifier |
| Signal classify | UNO Q | `sinewave`-style TinyML on-device |
| Proactive reasoning (burst) | **IQ8** hub (Hexagon v75) | Qwen2.5-0.5B GGUF / Qwen3-4B Genie (hybrid) |
| Personal memory | IQ8 | All-MiniLM-L6-v2 → SQLite |

**Aspirational target silicon (NOT on bench — mark clearly in external use):**

| Platform | Target SoC | Why it matters | Status |
|---|---|---|---|
| Smartwatch | **Snapdragon W5+ Gen 1** | Purpose-built low-power wearable platform | Not in fleet |
| Hearable / band | Low-power Snapdragon audio SoC | Always-on audio sensing | Not in fleet |

> **Honest framing:** the *low-power sensing + tiny-model gating + burst-to-hub
> reasoning* architecture is real and demonstrable on UNO Q + IQ8. The W5 line is
> the production target we're designing toward, not hardware we've benchmarked.

---

## SDK / Software Stack

| Layer | Choice |
|---|---|
| On-device TinyML | ONNX Runtime / TFLite Micro on the MCU |
| Wake gating | Streaming keyword spotter (`wake_word` project) |
| Sensor pipeline | UNO Q real-time control brain → AI brain handoff |
| Burst reasoning | IQ8 hub via llama.cpp (CPU) or Qwen3-4B Genie (NPU, hybrid) |
| Memory | SQLite + MiniLM embeddings (compact profile) |
| Power model | Tiny model always on; large model invoked only on a gated trigger |

---

## Demo Scenario

> The band notices an unusual resting-heart-rate trend across the afternoon and a
> long sedentary stretch. Instead of waiting to be asked, it fuses the signals
> on-device, wakes the hub for one burst of reasoning, and nudges: *"Your resting
> HR has been elevated since 2 PM and you haven't moved in 90 minutes — want a
> short walk reminder?"* **The vitals never left your wrist and the hub.**

---

## Where This Maps in the Repo

- **Directly reuses** the TinyML projects: `wake_word`, `gesture_recognition`,
  `sinewave` — these are already the wearable-scale building blocks.
- Reuses **AURA** memory for the compact personal profile and the burst-reasoning
  hybrid tunnel.

## Event / Workshop Hooks

- **Hackathon track:** "Proactive, not reactive" — a wearable demo that surfaces
  an insight without being prompted, using on-device gating.
- **Workshop (90 min):** train `hey_dragon` KWS, deploy to UNO Q, gate a burst
  call to the IQ8 hub.
- **Content:** blog — *"The low-power ladder: tiny model on the wrist, big model
  on the hub, nothing in the cloud."*

---

## Run the proxy

`wearable/` is the sensor-fusion and gating loop, running on the **IQ8 in place of the UNO Q**.
Sensors are **simulated** (deterministic IMU plus heart rate), so nothing here measures real
vitals or runs `hey_dragon`/gesture models yet. A windowed motion and heart-rate classifier
(plain arithmetic, no numpy) infers resting / walking / running / anomaly, writes an AURA
`Event` only when the context changes (2-window debounce), and calls the "big model" burst
only for an anomaly.

```bash
# from Wearable-AI (needs AURA on PYTHONPATH; stdlib otherwise)
PYTHONPATH=../AURA/src:. python -m wearable --db wearable.db
PYTHONPATH=../AURA/src:. pytest tests        # 5 pass
```

**Measured on a Dragonwing IQ-8275 (Qualcomm Linux 2.0, aarch64, Python 3.14):** 81 s of
sensor data (2025 samples, 40 two-second windows) produced 6 context events and 1 burst
(big-model duty 2.5%) in 0.017 s. The events were read back from the board's AURA memory
and match the scenario. The board's trimmed Python has no `statistics` module, so the
classifier uses plain arithmetic.

Not covered: real IMU/health sensors, TinyML models on an MCU, W5 silicon, and the hub-side
LLM that handles the burst (use `AI-Across-Devices/handoff` to move these events to a hub).
