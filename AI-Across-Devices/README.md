# AI Across Devices

### Theme: Seamless cross-device intelligence

> *Your AI doesn't live on one device. It follows you.*
>
> **One context. Many devices. No cloud round-trip.**

Enable AI experiences that move seamlessly across phones, wearables, XR
headsets, and edge platforms while **maintaining context and continuity** — the
memory, personalization, and in-flight task all travel with the user, and the
transfer stays on the **local network** rather than through a cloud broker.

This story is the *connective tissue* between the other stories: [AURA](../AURA/README.md)
is the single-device agent; this one shows the **same agent state** handed from
an IQ8 hub to an X Elite laptop to a wearable without losing the thread.

> **Status: two-node handoff implemented and verified** (IQ8 hub → PC, see
> [Run the handoff](#run-the-handoff)). Originally a narrative brief; buildable as a **two-node handoff** on the
> existing fleet (IQ8 ↔ X Elite ↔ IQ9) reusing the AURA `Event` contract and the
> Agents project's `--base-url` portability. Phone/wearable/XR nodes are
> **aspirational** until that silicon is on the bench (see below).

---

## Modules

| Module | What it does | Built on |
|---|---|---|
| **Shared memory** | A portable event/memory store (SQLite + MiniLM embeddings) that any node can read/write | AURA `memory/` |
| **Context transfer** | Serialize the active session (recent Events + task state) and hand it to the next device | AURA `core.events.Event` |
| **Cross-device orchestration** | Pick the right execution point per request; route reasoning to the most capable online node | Agents `--base-url` swap |
| **Local synchronization** | LAN-only sync (SSH tunnel / mDNS) — no cloud broker; state stays inside the trusted network | AURA hybrid-mode tunnel |
| **Personalized experiences** | The user profile + preferences ride along with the memory store | AURA personalization |

---

## Device & Model Mapping

**Real fleet (buildable now):**

| Node | Device | Role in the demo | Reasoning model |
|---|---|---|---|
| Hub | **IQ8** (QCS8275, Hexagon v75, ~11 GiB) | Always-on perception + memory owner | Qwen2.5-0.5B GGUF (CPU) / Qwen3-4B Genie (hybrid) |
| Laptop | **Snapdragon X Elite** PC (Hexagon v73) | High-quality reasoning when present | Qwen3-4B-Instruct-2507 W4A16 (Genie NPU) |
| Edge | **IQ9** (QCS9075, Hexagon v81) | Roomier compute; larger-model host | Gemma-4-12B GGUF (CPU) / Qwen3-4B Genie |

**Aspirational targets (not on bench — flag in any external deck):**

| Node | Target silicon | Role in the demo | Reasoning model | Status |
|---|---|---|---|---|
| Phone | Snapdragon 8-series (Hexagon NPU) | Mobile companion; carries context on the go, initiates handoffs | Qwen3-4B W4A16 (Genie NPU) / small GGUF (CPU) | Not in fleet — narrative only |
| Wearable | Snapdragon W5+ Gen 1 | Glanceable node; low-power sensing + notifications, bursts to hub | Tiny on-device classifier + `hey_dragon` KWS; reasoning via hub | See [Wearable AI Assistant](../Wearable-AI/README.md); not on bench |
| XR | Snapdragon XR2 Gen 2 | Spatial front-end; scene-aware queries handed to the fleet | Whisper STT + Qwen3-4B (Genie, on-headset or via hub) | See [XR-Powered Experiences](../XR-Experiences/README.md); not on bench |

> **Continuity model:** memory and personalization are owned by the hub (IQ8) and
> **replicated**, not centralized in cloud. Any node can go offline; the session
> survives on whichever node is present. Only grounded context — never raw
> sensor data — crosses the wire, matching AURA's privacy posture.

---

## SDK / Software Stack

| Layer | Choice |
|---|---|
| Reasoning (NPU) | QAIRT 2.47 · Genie / GenieX (Qwen3-4B W4A16) |
| Reasoning (CPU) | llama.cpp (GGUF fallback per node) |
| Memory | SQLite event log + All-MiniLM-L6-v2 embeddings |
| Transport | OpenAI-compatible HTTP · SSH reverse tunnel (loopback-only endpoints) |
| Portability | Single agent codebase, per-node `--base-url` / profile (Agents `agent_profiles.json`) |

---

## Demo Scenario

> A warehouse supervisor's IQ8 hub watches a loading bay all morning. She walks
> to her office and opens her X Elite laptop: *"Catch me up on the bay."* The
> laptop pulls the morning's Events from the hub over the local tunnel and
> answers with the **higher-quality** Qwen3-4B NPU model — same memory, better
> brain. Later, on the floor with only the IQ9 reachable, the same question is
> answered there. **The context never left the building.**

---

## Where This Maps in the Repo

- Reuses **AURA** (`../AURA`) for the Event contract, memory, and hybrid tunnel.
- Reuses **Agents** (`../Agents`) for the write-once/run-anywhere agent and
  per-device profiles — the `--base-url` swap *is* cross-device orchestration.

## Event / Workshop Hooks

- **Hackathon track:** "Hand off a live AI session between two Snapdragon devices
  without cloud." Judged on continuity + latency.
- **Workshop (90 min):** stand up the IQ8 hub, tunnel to X Elite, run the catch-up
  query on both backends, compare answers.
- **Content:** blog — *"Which processor should answer? Routing AI across a local
  fleet."*

---

## Run the handoff

`handoff/` is a stdlib-only module (plus AURA's `Event` and `MemoryStore`) that moves
grounded context between nodes. The hub serves a token-protected, read-only bundle bound
to loopback; the other node pulls it through an SSH tunnel. Raw-sensor attributes
(image, frame, audio, embedding...) are stripped before export, bundles carry a SHA-256
checksum, and imports are idempotent.

```bash
# hub (e.g. IQ8): copy AURA/src/aura and AI-Across-Devices/handoff next to the memory db
HANDOFF_TOKEN=<random> PYTHONPATH=. python3 -m handoff serve --db aura.db --port 8765

# laptop: tunnel, then pull ("catch me up on the bay")
ssh -N -L 18765:127.0.0.1:8765 <user>@<hub>
HANDOFF_TOKEN=<same> PYTHONPATH=../AURA/src:. python -m handoff pull --db laptop.db --url http://127.0.0.1:18765
```

Tests: `PYTHONPATH=../AURA/src:. pytest tests` (6 pass; needs `numpy` for AURA's store).

**Verified on hardware:** Dragonwing IQ-8275 (Qualcomm Linux 2.0, Python 3.14) served three
seeded Events; a Windows-on-Snapdragon PC pulled them through the tunnel (3 added, then
0 added on a repeat pull), `where_is("package")` answered from the pulled memory, a wrong
token returned 401, and the `image_path` attribute did not cross the wire. The board's
trimmed Python lacks `html`, so the server uses `socketserver` instead of `http.server`.
**Answering over pulled context:** `python -m handoff ask --db laptop.db --base-url
http://127.0.0.1:11434/v1 --model qwen2.5:3b "Where is the package?"` puts only the local
Events in the prompt and calls any OpenAI-compatible endpoint (llama.cpp, Ollama, GenieX), so
swapping `--base-url` is the cross-device routing step. Measured on the PC via Ollama
(not the NPU): Qwen2.5-3B answered "near door 2" and "Do not know" (name not in the data)
correctly; Qwen2.5-0.5B got both wrong, so use 3B or larger for the catch-up query.

Not yet validated: a Genie/Qwen3-4B NPU backend behind the same endpoint (no model cached
in GenieX on the bench PC), and the phone, wearable and XR nodes (aspirational silicon; the
wearable proxy runs on the IQ8, see [Wearable AI](../Wearable-AI/README.md)).
