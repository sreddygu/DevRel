# AURA Architecture

AURA is a **perceive → remember → reason → act** loop that runs entirely
on-device on the Arduino VENTUNO Q. Nothing leaves the board.

```
        +----------------------+
        |       Cameras        |
        +----------+-----------+
                   |
                   v
        +----------------------+          +----------------------+
        |    Vision Models     |          |     Microphone       |
        |     YOLO / VLM       |          +----------+-----------+
        +----------+-----------+                     |
                   |                                 v
                   v                       +----------------------+
        +----------------------+           |   Whisper  (STT)     |
        |   Event Generator    |           +----------+-----------+
        +----------+-----------+                      |
                   |                                  |
                   v                                  |
        +----------------------+                      |
        |   Memory Database    |<---------------------+
        | Vector + Metadata    |
        |  (SQLite + Chroma)   |
        +----------+-----------+
                   |
                   v
        +----------------------+     +----------------------+
        |     Local LLM        |---->|      TTS (MeloTTS)   |---> Speaker
        |   Gemma / Qwen       |     +----------------------+
        +----------+-----------+
                   |
                   v
        +----------------------+
        |     Agent Layer      |
        |  (LangGraph + tools) |
        +----------+-----------+
                   |
                   v
        +----------------------+
        |  Smart Home / Robot  |
        |  lights, relays, …   |
        +----------------------+
```

## Data contract: the `Event`

Every module speaks in `aura.core.events.Event` — this is the seam that lets
milestones be built and tested independently.

| Field        | Meaning                                             |
|--------------|-----------------------------------------------------|
| `event`      | Human-readable description ("Person entered room")  |
| `timestamp`  | ISO-8601 time (defaults to now, UTC)                |
| `type`       | `detection` / `speech` / `action` / `scene`         |
| `entities`   | Named things involved (`["package"]`, `["Neha"]`)   |
| `location`   | Where it happened (`"study room"`)                  |
| `source`     | `vision` / `speech` / `agent` or a device id        |
| `confidence` | Model confidence `[0,1]` when known                 |
| `attributes` | Free-form extras (bbox, image path, embedding ref)  |
| `id`         | Stable uuid4                                        |

Minimal form (as in the roadmap):

```json
{ "timestamp": "10:24", "event": "Person entered room" }
```

## Modules

| Package            | Role                              | Milestone | Key deps (extra)          |
|--------------------|-----------------------------------|-----------|---------------------------|
| `aura.core`        | Event contract + pipeline loop    | —         | stdlib                    |
| `aura.vision`      | Camera + YOLO/VLM → Events        | 1 Eyes    | opencv, onnxruntime       |
| `aura.speech`      | Whisper STT + MeloTTS             | 2 Ears    | openai-whisper, sounddevice |
| `aura.memory`      | SQLite + vector recall            | 3 Memory  | chromadb (sqlite is stdlib) |
| `aura.agent`       | Local LLM + actuator tools        | 4/5       | httpx, langgraph          |
| `aura.dashboard`   | FastAPI + Streamlit UI            | —         | fastapi, uvicorn, streamlit |

## Design principles

- **Local-first / privacy-first.** No cloud calls. The LLM is an on-device
  llama.cpp / Genie server reached over `127.0.0.1`.
- **Light base install.** `import aura` needs only `numpy` + `pydantic`. Heavy
  runtimes are optional-dependency groups, imported *lazily* inside methods, so
  the repo clones and imports on a bare on-device interpreter.
- **One contract, many producers/consumers.** Everything flows through `Event`.
- **Dependency injection.** `AuraPipeline` takes its collaborators as arguments,
  so a partial system (e.g. vision + memory, no LLM yet) runs during early
  milestones.

## Dual-brain target (VENTUNO Q)

The VENTUNO Q pairs an AI-inference SoC with a real-time microcontroller.
AURA's perception + reasoning run on the Linux/AI side; Milestone 5 actuation
(relays, motors, robot) is delivered through the real-time MCU side. See
`docs/ROADMAP.md` for the phasing.
