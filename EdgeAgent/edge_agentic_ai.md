# Edge Agentic AI & Local Agents — Why It Matters

> Conceptual companion to this project. `README.md`/`usage.md` tell you **how** to
> run the agent; this note explains **what** an agent is, what "edge" adds, and
> **why** running agents locally on devices like the Snapdragon X Elite and the
> IQ8/IQ9 is worth doing. That frames the hands-on `agent`.

## 1. What is an "agent" (vs. a chatbot)?

A plain LLM chat turn is **one-shot**: prompt in, text out. An **agent** wraps the
model in a loop that lets it *act* on the world and *react* to what it observes:

```
        ┌──────────────────────────────────────────┐
        │                                            │
   goal ─▶  THINK  ─▶  ACT (call a tool)  ─▶  OBSERVE ─┘   …repeat until done ─▶ answer
```

This is the **ReAct** pattern (Reason + Act). The model decides *one* next action,
a tool runs it, the result is fed back, and the model decides again. That loop is
exactly what `agent.py` implements: each turn the model emits one JSON object —
`{"thought": …, "tool": …, "args": …}` to act, or `{"thought": …, "answer": …}`
to finish — and the harness runs the tool and loops.

The difference that matters: an agent can **gather what it needs before answering**
and **chain several steps toward a goal**, instead of guessing in one shot.

## 2. What makes it *agentic*?

Four properties, all visible in this project's lab:

1. **Tool use** — the model can reach beyond its own weights: do real arithmetic
   (`calculator`), read a file (`read_file`), list directories (`list_dir`), check
   file metadata (`stat_file`), get a portable device profile (`sys_info`),
   inspect the device via a read-only shell (`run_shell`), and get the real time
   (`now`). The model's job shifts from *knowing* to *deciding which tool to use*.
2. **Multi-step planning** — "Profile this device: hostname, CPU arch, cores, RAM,
   then summarize" can be done in one step with `sys_info`, or via multiple
   read-only shell calls (e.g., `hostname`, `lscpu`, `free -h`) where available.
3. **Observe-and-adapt** — each tool result re-enters the context, so the next
   step is conditioned on what actually happened (including errors it can recover
   from).
4. **Bounded autonomy** — the agent runs on its own up to `--max-steps`, but only
   inside guardrails (read-only shell allowlist, whitelisted calculator, capped
   output). Autonomy *with* constraints is the whole game on a real device.

## 3. What "edge" adds

**Edge** = the model and the agent run **on the device** (or on a local host next
to it), not in a cloud datacenter. In this project that's the Snapdragon X Elite
host PC and the IQ8/IQ9 boards — the agent talks to a *local* model server
(`llama.cpp` on CPU, or `genie_server.py` on the X Elite NPU), never to a remote
API.

That single architectural choice is what the whole project is built around: the
agent **never loads a model itself** — it speaks HTTP to a local OpenAI-compatible
server, so the same agent code runs unchanged from laptop to edge board with only
`--base-url` changing.

## 4. How does an agent framework reach the NPU?

A common question: *"Can I use Ollama / LangChain / some agent SDK to run the
agent on the NPU?"* The answer hinges on one fact:

> The Hexagon NPU only speaks one stack — **QAIRT/Genie** (QNN context binaries).
> And Genie is a **text-generation** API (`GenieDialog_query`), **not an agent
> API**: it gives you a chat/dialog turn, not a tool-calling ReAct loop.

So there is **no first-party "agent API" that runs the agent loop on the NPU**.
The agent loop (THINK → ACT → OBSERVE) always runs on the **host CPU** in Python;
only the **token generation** happens on the NPU. (This also answers the Ollama
question: Ollama's backend is `llama.cpp`/GGUF and has no Hexagon/QNN backend, so
Ollama on the X Elite runs on **CPU**, never the NPU.)

Given that, how does an agent framework reach the NPU's text-gen? Three layers,
cheapest-effort first:

**1. Any OpenAI-compatible agent API → the shim → NPU (what this project does).**
Because `genie_server.py` exposes `/v1/chat/completions`, *any* agent SDK or
framework that lets you set a base URL can drive the NPU — it can't tell the shim
apart from OpenAI:

| Agent API / framework | How it reaches the NPU |
|---|---|
| OpenAI Python SDK | `OpenAI(base_url="http://127.0.0.1:8081/v1")` |
| LangChain / LlamaIndex | `ChatOpenAI(base_url=…, model="qwen3-4b-genie")` |
| Qwen-Code / Codex CLI | custom provider → `http://127.0.0.1:8081/v1` |
| this project's `agent.py` | `--profile npu` |

The shim **is** the "agent API to NPU" adapter. Nothing else Qualcomm ships does
the loop for you.

**2. The Genie C/C++ API directly (skip HTTP).** `libGenie` / `GenieDialog` is the
native API to the NPU. You could build the agent loop in C++ against it — no shim,
lower latency — but you re-implement everything `agent.py` does. Only worth it for
a production C++ app.

**3. A different NPU runtime: ONNX Runtime GenAI + QNN Execution Provider.** The
one genuinely different path: ONNX Runtime can target Hexagon via the QNN EP, and
`onnxruntime-genai` gives a `generate()` API you could build an agent on. It's a
*parallel* stack to Genie, and LLM support on the QNN EP is still narrow — treat
it as exploratory, not a drop-in.

**The takeaway:** the best answer is the one this project already uses — an
OpenAI-compatible agent framework pointed at `genie_server.py`. If you want a
richer agent than `agent.py` (multi-file editing, MCP tools, …), the move is
**not** a new NPU API; it's pointing LangChain / the OpenAI SDK / Qwen-Code at the
`:8081` shim — exactly the pattern of pointing a harness at a local server.

## 5. Why edge / local agents matter

| Benefit | Why it matters on a device like IQ8 |
|---|---|
| **Privacy & data residency** | Prompts, files, camera/sensor data never leave the device. Critical for industrial, medical, and Qualcomm-customer deployments where data *can't* go to a cloud. |
| **Latency** | No network round-trip. The control loop runs at local speed — essential for anything reacting to the physical world. |
| **Offline / intermittent connectivity** | Factory floors, vehicles, remote sites, field devices. The agent keeps working with no internet. |
| **Cost & scale** | No per-token API bill and no per-device cloud dependency. Inference cost is the hardware you already shipped. |
| **Reliability & autonomy** | The device keeps its "intelligence" even when the cloud is down or unreachable. |
| **Power efficiency** | On the X Elite, the **NPU** (Hexagon HTP) runs the model far more efficiently than CPU — the point of the Genie/QAIRT path in this project. |

The trade-off — and the reason this project exists — is that edge means **small
models and tight RAM**. IQ8 has ~11 GiB; the proven-safe fit is the effective-4B
Gemma 4 (`gemma-4-E4B-it-Q4_K_M.gguf`). Building an agent that's *useful* on a 4B
model is a real engineering constraint, not a toy one.

## 6. The design consequences (why this agent is built the way it is)

Edge constraints directly shaped `agent.py`. These are the lessons worth taking
away:

- **ReAct JSON loop, not OpenAI function-calling.** Small edge models are
  unreliable at native tool/function-calling (it produced "tool_call garbage" on
  IQ8). A plain "reply with one JSON object" contract is far more robust on a 4B
  model and needs no special server flags.
- **The model is decoupled from the agent.** The agent only speaks
  `/v1/chat/completions`. Swap the backend (CPU `llama.cpp` ↔ NPU Genie) or the
  host (X Elite ↔ IQ8 ↔ IQ9) by changing one URL. Write once, run everywhere.
- **Tools are small, safe, side-effect-light.** They run on a real device, so the
  shell tool is **read-only and allowlisted** and refuses shell metacharacters.
  Bounded autonomy beats unbounded power.
- **Everything is capped** — tokens, output length, step count — because RAM and
  context are scarce at the edge.
- **Portability is the proof.** If it runs against E4B on the X Elite, the *same*
  model and code run on IQ8. Proving on the bigger host de-risks the board.

## 7. Where this is going

The same loop scales up the moment the hardware does: bigger local models, more
tools (HTTP fetch, device actuation, vector search/RAG over local notes),
multi-agent coordination, and longer-horizon autonomy — all still **on-device**.
The skills from this lab (tool design, guardrails, the observe-and-adapt loop,
backend portability) are exactly the skills those systems are built from.

## See also

- [`README.md`](README.md) — how the agent works and how to run it (CPU, NPU, Podman)
- [`usage.md`](usage.md) — CPU and NPU bring-up steps
- [`agent.py`](agent.py) — the implementation of everything above
- [`benchmark_cpu_vs_npu.ps1`](benchmark_cpu_vs_npu.ps1) — CPU vs. NPU latency comparison
