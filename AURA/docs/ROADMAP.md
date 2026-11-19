# AURA Development Roadmap

**Phase 1 MVP goal:** an offline agent that can **See ✅ · Hear ✅ · Remember ✅ ·
Answer ✅ · Act ✅** — entirely on-device.

Status legend: ⬜ not started · 🟨 in progress · ✅ done. All five milestones
are implemented and PC-validated. Physical hardware validation (VENTUNO Q) remains
for Milestone 5 (ROS2 + relay hardware).

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

**Snapdragon X Elite validation:** pi `0.74.2` successfully used the GenieX
OpenAI-compatible server with Gemma 4 E4B Q4_0 on the NPU, including a complete
`bash` tool round-trip that executed `hostname` and returned the verified result.
See `docs/PI_GENIEX.md` and `scripts/test_pi_geniex.ps1`.

---

## Milestone 5 — 🤖 Action  ✅

Control lights, relays, smart devices, and a mobile robot via agent tools,
delivered through the VENTUNO Q real-time MCU side.

- `aura.agent.tools.SmartHomeTransport` — injectable protocol for light/relay/scene
  adapters (MQTT, Home Assistant, serial relay, etc.).
- `aura.agent.tools.MockSmartHomeTransport` — hardware-free stand-in for tests.
- `aura.agent.tools.smart_home_tools()` — returns `set_light` and `run_scene`
  tools backed by a transport; `Tool.to_openai_spec()` exposes each as an
  OpenAI function-calling spec.
- `aura.agent.llm.LocalLLM.act(command, tools, context)` — tool-calling loop:
  sends command + tool specs to the LLM, executes called tools, feeds results
  back, loops up to `max_rounds`, returns `(final_answer, action_events)`.
- `aura.agent.robot.SafeRobotController` — allowlisted motion directions, bounded
  speed/duration, automatic stop, latched emergency stop, and action auditing.
- `aura.agent.robot.Ros2CliTransport` — injectable ROS2 `/cmd_vel` adapter with
  no shell invocation and bounded publish timeouts.
- `AuraPipeline.act(command)` — retrieves context via memory recall, delegates
  to `LocalLLM.act`, persists action Events to memory.

**Example:** *"Turn on the workshop lights."*

**Definition of done:** a voice/text command selects and invokes the right tool,
the device actuates, and the action is remembered.

**Current status (PC-validated + VENTUNO Q ready):** smart-home seam, robot seam,
and agent tool-calling loop fully implemented and hardware-free tested. Physical
hardware readiness additions:

- **ROS2 topic naming** — `AURA_ROBOT_TOPIC` (default `/cmd_vel`) and
  `AURA_ROBOT_MAX_*` safety limits are now env-configurable via `Settings`.
- **Physical emergency-stop wiring** — `SysfsGpioReader` reads an active-low
  GPIO button via `/sys/class/gpio/`; `watch_emergency_stop()` polls it on a
  daemon thread and latches `SafeRobotController.emergency_stop()` on trigger.
  Enabled by setting `AURA_ROBOT_EMERGENCY_GPIO=<pin>`.
- **End-to-end VENTUNO Q deploy script** — `deploy/ventuno_q/aura_e2e.py`
  wires the full perceive→remember→reason→act loop with the real
  `SafeRobotController` + `LocalLLM.act()` tool-calling loop +
  `SerialRelayTransport` (MCU serial relay) and physical e-stop watching.

See `examples/act_demo.py`, `tests/test_action.py`, `tests/test_robot.py`,
and `deploy/ventuno_q/aura_e2e.py`.

---

## Demo scenario (Phase 1 target)

> User leaves the room → camera records events → AURA stores observations →
> user returns and asks *"What happened while I was gone?"* → AURA answers:
> *"Two people entered the room, a package was delivered, and the lights were
> switched off at 4:15 PM."*

This exercises Milestones 1 (see) → 3 (remember) → 4 (reason/answer), with
2 (voice) and 5 (action) completing the loop.
