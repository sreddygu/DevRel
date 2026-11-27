# Multiverse of Developers

### Theme: One platform, many developer personas

> *Same silicon. Same toolchain. Seven very different builders.*
>
> **Student · Maker · Startup · Embedded · Robotics · AI Engineer · Enterprise.**

Demonstrate how students, makers, startups, embedded developers, robotics
developers, AI engineers, and enterprises can all build on Snapdragon
technologies. This is the **meta / audience-mapping** story: it doesn't add a new
technical pipeline — it re-frames the other stories through each persona's lens, so
event organizers and BU teams can point any audience at the right entry project.

> **Status: framing + routing brief.** Every persona below maps to a project that
> **already exists** in this repo. This README is the index that turns "who's in
> the room?" into "start them here."

---

## Modules → Persona Routing

| Module (persona) | What they want | Start here (real project) | Device |
|---|---|---|---|
| **Education** (students) | Understand concepts fast, cheap hardware | `../Developer-Journey` + `../sinewave` | X Elite PC / UNO Q |
| **Makers** | Build something cool this weekend | `../wake_word` (`hey_dragon`) + `../gesture_recognition` | Arduino UNO Q |
| **IoT / Embedded** | Reliable on-device inference, tight resources | `../Wearable-AI` + `../VSaaS` | UNO Q / IQ8 |
| **Robotics** | Perceive → decide → act loop, real actuators | `../AURA` (Milestone 5 Action) | VENTUNO Q / IQ8 |
| **AI applications** (AI engineers) | Full LLM/RAG/agent stack on-device | `../Edge-AI-for-Everyone` + `../Agents` | X Elite / IQ8 / IQ9 |
| **Startup enablement** | Ship a product, prove it on real edge HW | `../AURA` + `../EdgeAgent` | IQ8 / IQ9 |
| **Hackathons** | A framed challenge with a clear win condition | any story's "Hackathon track" section | full fleet |

---

## Device & Model Mapping (by persona reach)

**Real fleet — matched to persona budget/skill:**

| Persona | Typical device | Typical model | NPU? |
|---|---|---|---|
| Student / Maker | Arduino UNO Q, X Elite PC | Tiny GGUF (0.5B), ONNX TinyML | On-device TinyML |
| Embedded / IoT | IQ8 (QCS8275, v75) | Qwen2.5-0.5B GGUF; YOLO/YAMNet QNN | ✅ vision NPU |
| Robotics | VENTUNO Q / IQ8 | YOLOv8n + Qwen3-4B (hybrid) | ✅ |
| AI Engineer | X Elite (v73), IQ9 (v81) | Qwen3-4B W4A16 Genie; Gemma-4-12B GGUF | ✅ |
| Enterprise / Startup | IQ8 + IQ9 fleet | full AURA multimodal stack | ✅ |

> **No aspirational hardware needed for this story** — its whole point is that the
> *existing* fleet already covers every persona. Where a persona would ideally use
> phone/XR/wearable silicon, route them to [AI Across Devices](../AI-Across-Devices/README.md),
> [XR-Powered Experiences](../XR-Experiences/README.md), or [Wearable AI Assistant](../Wearable-AI/README.md),
> which carry those aspirational-silicon caveats.

---

## SDK / Software Stack (shared across all personas)

| Layer | Choice |
|---|---|
| NPU | QAIRT 2.51 · QNN · Genie / GenieX |
| CPU | llama.cpp (GGUF), ONNX Runtime, TFLite Micro |
| Agent / app | stdlib agent (`../Agents`), AURA pipeline (`../AURA`) |
| The point | **one toolchain**; the persona changes the *entry project*, not the platform |

---

## Demo Scenario

> A regional event has students, two robotics teams, a healthcare startup, and a
> handful of embedded engineers in one room. The organizer opens with [Developer
> Journey](../Developer-Journey/README.md)
> (everyone gets a working setup), then splits the room: makers to `wake_word`,
> robotics to AURA's action loop, the startup to AURA + EdgeAgent, AI engineers
> to Edge-AI-for-Everyone. **Same platform, seven parallel wins by day's end.**

---

## Where This Maps in the Repo

This story is the **atlas** for the other six plus the standalone building blocks:
`AURA`, `Agents`, `LLM`, `VSaaS`, `wake_word`,
`gesture_recognition`, `sinewave`. Each persona row above is a live link to a
project that already runs on the fleet.

## Event / Workshop Hooks

- **Event design template:** use this table to pre-assign tracks from
  registration data ("who's coming?" → "which project?").
- **Booth flow:** one demo per persona, all on the same IQ8/IQ9 fleet, to show
  breadth without a hardware zoo.
- **Content:** persona landing pages, each linking to its start-here project.
