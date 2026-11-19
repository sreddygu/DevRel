# Developer Journey: From Setup to AI Success

### Theme: First 30 minutes to first AI application

> *From unboxing to your first token — before the coffee gets cold.*
>
> **Setup → sample → deploy → share.**

Guide developers from device setup to building, deploying, and sharing their
first AI-powered application. This is the **onramp** story: it's not about the
most advanced demo, it's about the *time-to-first-success* — the single metric
that decides whether a developer stays. Every friction point removed here pays
off in every other story.

> **Status: buildable now, assembled from proven pieces.** The fastest verified
> path today is the **Agents** project on a Snapdragon X Elite host: prebuilt
> ARM64 llama-server + stdlib agent = first answer in minutes, no toolchain
> build. This story packages that into a guided 30-minute journey.

---

## Modules

| Module | What it does | Built on |
|---|---|---|
| **Device setup** | Get the board/host online, drivers + runtime in place | Agents Windows-ARM64 setup notes |
| **Sample applications** | A working app on first run — no "build the world" first | Agents `agent.py` (stdlib-only) |
| **AI workflows** | The perceive/reason/act pattern shown minimally | AURA loop (lite) |
| **Deployment** | Run the same app on a second device via `--base-url` | Agents portability |
| **Optimization** | One concrete win (pick the right quant / backend) | LLM sizing + `HEXAGON_NPU.md` |
| **Community onboarding** | Share the result; a repeatable "hello, NPU" others can fork | This curriculum |

---

## The 30-Minute Journey

| Minute | Step | Command / action |
|---|---|---|
| 0–5 | **Verify the host** | `python -c "import platform; print(platform.machine())"` → confirm **ARM64** (the X Elite x86-emulation trap) |
| 5–12 | **Get a model server** | Download prebuilt `llama-bXXXX-bin-win-cpu-arm64.zip`; run `llama-server.exe -m ...E4B...gguf` |
| 12–18 | **First answer** | `python agent.py "What is 12.5% of 840?"` |
| 18–25 | **See it reason** | `python agent.py -v "..."` → watch THINK → ACT → OBSERVE |
| 25–30 | **Deploy elsewhere** | `python agent.py --base-url http://<IQ8_IP>:8080 "..."` — same code, new device |

---

## Device & Model Mapping

**Real fleet (the actual onramp):**

| Stage | Device | Model | Why |
|---|---|---|---|
| First success | **Snapdragon X Elite PC** | Gemma-4-E4B Q4_K_M (llama.cpp CPU) | No build needed; prebuilt ARM64 binary |
| Second device | **IQ8** (QCS8275) | same E4B GGUF | Proves portability via `--base-url` |
| Stretch goal | **X Elite NPU** (v73) | Qwen3-4B W4A16 (Genie) | First taste of NPU acceleration |

> **Documented traps this journey defuses (all real, all bench-verified):**
> - `pip install llama-cpp-python` ships x86 AVX wheels that **crash** on ARM64
>   (`0xc000001d`) — use the **prebuilt ARM64 binary** instead.
> - Behind **Netskope**, `curl`/`winget` fail TLS; **Python with the CA bundle**
>   (or `pip`) works. (See the fleet's Netskope CA note.)
> - Genie bundles must live on **plain disk, not Dropbox** (mmap blocked).

---

## SDK / Software Stack

| Layer | Choice |
|---|---|
| Model server | Prebuilt llama.cpp ARM64 (`llama-server.exe`) — no toolchain |
| Agent | `agent.py` — stdlib only (`urllib`, `json`), zero pip installs |
| NPU (stretch) | QAIRT 2.47 · Genie (`genie_server.py` shim) |
| Env | Native ARM64 Python (project venv) |

---

## Demo Scenario

> A workshop attendee opens a fresh X Elite laptop. Thirty minutes later they've
> gotten their first local LLM answer, watched the agent chain three tools to
> profile the machine, pointed the *same* script at an IQ8 across the room, and
> pushed their forked "hello, NPU" to the community repo. **No cloud key, no
> build farm, no wall.**

---

## Where This Maps in the Repo

- **Primary:** `../Agents` — the stdlib agent + Windows-ARM64 bring-up is the
  literal fast path; `usage.md` has the copy/paste steps.
- **Model build (if they want it):** `../LLM/README.md`.
- **Next step after success:** graduate into [Edge AI for Everyone](../Edge-AI-for-Everyone/README.md).

## Event / Workshop Hooks

- **Every event opens with this.** It's the icebreaker session that guarantees
  each attendee has a working setup before the advanced tracks.
- **Content:** a timed "first 30 minutes" video + a printable one-page checklist.
- **Metric to report:** median time-to-first-token per attendee.
