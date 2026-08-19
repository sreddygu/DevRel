# AURA Development Roadmap

**Phase 1 MVP goal:** an offline agent that can **See ✅ · Hear ✅ · Remember ✅ ·
Answer ✅** — entirely on-device.

Status legend: ⬜ not started · 🟨 in progress · ✅ done. Milestones 1 (Eyes),
2 (Ears/Voice), 3 (Memory), and 4 (Brain) are implemented and validated;
Milestone 5 (Action) still ships as importable stubs whose methods raise
`NotImplementedError("Milestone 5 …")`.

---

## Milestone 1 — 👁️ Eyes  ✅

Connect a camera, run YOLO detection, capture frames, generate scene
descriptions, and emit Events.

- `aura.vision.camera.Camera` — open a webcam/CSI/RTSP source (or an image /
  image-directory, for hardware-free runs), yield frames. Lazy `cv2`.
- `aura.vision.detector.Detector` — YOLOv8 ONNX inference (self-contained
  decode + NMS) → `Detection`s → `Event`s (`Detector.to_events`). Lazy
  `onnxruntime`/`numpy`; pass `providers=["QNNExecutionProvider"]` to target the
  Hexagon NPU.

**Output:**
```json
{ "timestamp": "10:24", "event": "Person entered room" }
```

**Definition of done:** `AuraPipeline.run` captures from the configured camera
and writes detection Events to the memory store in a loop. ✅ PC-validated on the
canonical `bus.jpg` with a real `yolov8n.onnx` ("4 people and a bus"), and
**ported to the IQ8 Hexagon NPU (HTP V75)** via `qnn-net-run` + a `yolov8_det_w8a8`
DLC (~1.35 s/frame on-device). See `examples/eyes_demo.py`, `tests/test_vision.py`,
and `docs/NPU_SETUP.md`.

---

## Milestone 2 — 👂🗣️ Ears / Voice  ✅

Connect a microphone, transcribe with Whisper, handle basic voice commands, and
speak responses via TTS.

- `aura.speech.stt.SpeechToText` — record + Whisper transcribe → speech `Event`.
- `aura.speech.tts.TextToSpeech` — synthesize (piper) + play.

Both engines are reached through an injectable `backend` seam, so tests run on
the base install and on-device drivers can swap in prebuilt aarch64 binaries
(whisper.cpp `whisper-cli`, `piper`) with no Python wheels.

**Examples:** *"What do you see?"* · *"What happened today?"*

**Definition of done:** a spoken question is transcribed, routed to the agent,
and the answer is spoken back — all locally. ✅ Full STT→TTS round-trip verified
**on the IQ8** (whisper.cpp `ggml-base.en` + piper `en_US-lessac-medium`). See
`examples/listen_demo.py` and `tests/test_speech.py`.

---

## Milestone 3 — 📚 Memory  ✅

Store events, images, conversations, and object locations; support structured
and semantic queries.

- `aura.memory.store.MemoryStore` — SQLite log + object last-seen table
  (stdlib, **done**), plus Chroma vector recall (`memory` extra). Without the
  extra, `recall` degrades gracefully to a SQLite keyword search.
- `MemoryStore.query` (time/entity/type), `.recall` (semantic), `.where_is`.

**Query examples:** *Who came today?* · *Where is my backpack?*

**Definition of done:** Events persist across restarts; `where_is("laptop")`
returns the last-seen location Event. ✅ (see `examples/memory_demo.py` and
`tests/test_memory.py`).

---

## Milestone 4 — 🧠 Brain  ✅

Add a local LLM (Gemma/Qwen via on-device llama.cpp / Genie) for summaries,
reasoning, and contextual answers.

- `aura.agent.llm.LocalLLM` — OpenAI-compatible chat client (`agent` extra:
  httpx), `.summarize(events)`, `.answer(question, context)`. **Done** — POSTs
  to `{base_url}/v1/chat/completions`; a `transport` hook lets tests mock it.
- `AuraPipeline.ask` — retrieve relevant Events (`memory.recall`) → LLM →
  grounded answer. **Done**.

**Example:** *"The package arrived at 2 PM and remained on the front table."*

**Definition of done:** *"Summarize today's events."* produces a correct local
summary grounded in the stored Events. ✅ (see `examples/ask_demo.py` and
`tests/test_agent.py`). Requires a local LLM server (e.g. `llama-server`)
reachable at `AURA_LLM_BASE_URL`.

---

## Milestone 5 — 🤖 Action  ⬜

Control lights, relays, smart devices, and a mobile robot via agent tools
(LangGraph), delivered through the VENTUNO Q real-time MCU side.

- `aura.agent.tools.Tool` + `default_tools()` — `set_light`, `run_scene`,
  `move_robot` (each action is recorded as an `action` Event).

**Example:** *"Turn on the workshop lights."*

**Definition of done:** a voice/text command selects and invokes the right tool,
the device actuates, and the action is remembered.

---

## Demo scenario (Phase 1 target)

> User leaves the room → camera records events → AURA stores observations →
> user returns and asks *"What happened while I was gone?"* → AURA answers:
> *"Two people entered the room, a package was delivered, and the lights were
> switched off at 4:15 PM."*

This exercises Milestones 1 (see) → 3 (remember) → 4 (reason/answer), with
2 (voice) and 5 (action) completing the loop.
