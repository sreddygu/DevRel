# EdgeAgent: a tiny, portable tool-using LLM agent for local & edge devices (X Elite CPU/NPU → IQ8 → IQ9)

A minimal ReAct-style agent that calls tools (calculator, now, read_file,
list_dir, stat_file, sys_info, run_shell) on top of a local LLM. The point of
this project is **portability**: write the
agent once, prove it on a **Snapdragon X Elite host PC**, then run the **same
code** on the **IQ8**, **IQ9**, or any edge device — with the same model, or a
different one per device. Usually only one thing changes — the `--base-url`.

This project supports two backends:
- **CPU (non-NPU):** `llama.cpp` server (default `http://127.0.0.1:8080`)
- **NPU (X Elite):** `genie_server.py` shim over QAIRT/Genie (default `http://127.0.0.1:8081`)

## Project boundaries

- The root-level `agent.py`, UI, evaluation scripts, model-server shim, profiles,
  launchers, and usage guides form the lightweight **EdgeAgent** project.
- The root-level `devrel_agent.py`, `devrel_local.py`, and `devrel_tools.py` add
  an optional standard-library-only DevRel workflow to EdgeAgent.
- `devrel_runtime/` is a separate packaged DevRel client with its own source,
  tests, samples, and documentation. Review and commit it separately from the
  lightweight EdgeAgent files.
- `../qli_dogfooding/` is a separate project-level workspace and must be
  reviewed and committed independently from EdgeAgent.
- `backup/`, `workspace/`, virtual environments, logs, and audit notes are
  local evidence or working data and are excluded from source control.

See [`usage.md`](usage.md) for both **CPU** and **NPU** bring-up steps,
[`usage_podman.md`](usage_podman.md) for running the agent in a container, and
[`benchmark_cpu_vs_npu.ps1`](benchmark_cpu_vs_npu.ps1) for a simple side-by-side
latency check. For the *why* behind this project — what an agent is, what "edge"
adds, and why local agents matter — read [`edge_agentic_ai.md`](edge_agentic_ai.md).

## How it works

- The agent never loads a model. It speaks HTTP to a **local
  OpenAI-compatible server** (`/v1/chat/completions`) — `llama.cpp` on CPU, or
  `genie_server.py` on the NPU — exactly like `../LLM/test_gemma4.py`.
- The model replies with a single JSON object each turn — either
  `{"thought": "...", "tool": "...", "args": {...}}` to act, or
  `{"thought": "...", "answer": "..."}` to finish. We parse it, run the tool,
  feed the result back, and loop until it answers. This **ReAct JSON loop** is
  far more reliable on a small edge model than OpenAI function-calling (which
  produced "tool_call garbage" on IQ8).
- Every step has a visible **THINK → ACT → OBSERVE** trace (with `-v`), so you
  watch the agent reason, take one action, see the result, and decide the next
  step — it chains multiple tool calls toward a goal rather than one-shot
  chatting.
- Stdlib only (`urllib`, `json`, `argparse`, `subprocess`) — no pip installs.

## The model (why it fits IQ8 / IQ9)

Default model: **`gemma-4-E4B-it-Q4_K_M.gguf`** (effective-4B Gemma 4, ~4.7 GB
GGUF — 7.5B params, E4B effective compute).

IQ8 has **~11 GiB RAM** — the *tightest* target in this project. The E4B Q4_K_M
GGUF is the proven-safe fit there; the 12B is tight and the 26B stalls the board.
Sizing the model for the smallest device means it also fits the roomier IQ9.
Proving the agent against E4B on the X Elite guarantees the *same* model loads
and runs on both IQ8 and IQ9.

> Verified end-to-end on the X Elite host: all tools plus the
> direct-answer path work against this model via llama-server.

## 1. Start the model server

Same llama.cpp server on both machines — see `../LLM/README.md` to build it.

**On the X Elite host (do this first):**

```bash
~/llama.cpp/build/bin/llama-server \
  -m ~/models/gemma4/gemma-4-E4B-it-Q4_K_M.gguf \
  --host 127.0.0.1 --port 8080 --ctx-size 2048 --threads 8
```

**On the IQ8 (later) — safe, local-only settings:**

```bash
pkill -f llama-server || true
nohup ~/llama.cpp/build/bin/llama-server \
  -m ~/models/gemma4/gemma-4-E4B-it-Q4_K_M.gguf \
  --host 127.0.0.1 --port 8080 \
  --threads 4 --threads-batch 4 \
  --ctx-size 1024 --batch-size 256 --ubatch-size 64 \
  --parallel 1 \
  > ~/logs/llama_server_gemma4_$(date +%Y%m%d_%H%M%S).log 2>&1 &
```

> Note: this llama-server build rejects `--no-ui` and `--reasoning` — leave them
> out. Run `llama-server --help` to confirm what your build supports.

### Windows ARM64 host (Snapdragon X Elite PC)

On a **native ARM64 Windows** host you do **not** need to build llama.cpp — grab
the official prebuilt ARM64 binary and skip the toolchain entirely. Two traps make
this the *only* reliable path:

- **Don't use `pip install llama-cpp-python`.** The system `python.exe` on these
  boxes is usually **x86-64 under emulation** (`python -c "import platform;
  print(platform.machine())"` prints `AMD64`). Every available wheel — even into
  an ARM64 venv — ships **x86 AVX binaries** that load the model and then crash
  with `OSError [WinError -1073741795]` (`0xc000001d`, illegal instruction) the
  moment a CPU kernel runs. There is no prebuilt ARM64-Windows wheel.
- Use a **native ARM64 Python**. On this repo, prefer the project venv:
  `.\.venv\Scripts\Activate.ps1` then run `python ...` (it should print `ARM64`).

Get the prebuilt server — download the `llama-bXXXX-bin-win-cpu-arm64.zip` asset
from <https://github.com/ggml-org/llama.cpp/releases/latest>, unzip it, and run
its `llama-server.exe` with the same flags as above:

```powershell
.\llama.cpp-win-arm64\llama-server.exe `
  -m .\models\gemma-4-E4B-it-Q4_K_M.gguf `
  --host 127.0.0.1 --port 8080 --ctx-size 2048 --threads 8
```

Then run the agent with the **ARM64** interpreter (project venv):
`.\.venv\Scripts\Activate.ps1` then `python agent.py -v "What is 12.5% of 840?"`

> Behind a TLS-intercepting proxy (e.g. Netskope), `curl` may fail to download
> the release while Python succeeds — point Python at the proxy's CA bundle via
> `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE` (or `ssl.create_default_context(cafile=...)`).

Sanity check (either host): `curl -s http://127.0.0.1:8080/v1/models`

## 2. Run the agent

For developer bring-up and Qualcomm AI-stack onboarding, use the read-only
DevRel entry point described in [`DEVREL_AGENT.md`](DEVREL_AGENT.md):

```bash
python3 devrel_agent.py --profile cpu -v \
  "Assess this machine for Qualcomm NPU model bring-up."
```

It adds structured intake, dependency-free local hardware and SDK diagnostics,
loopback model-server checks, and evidence-based runtime selection without
enabling installation, deployment, flashing, or arbitrary command execution.

**On the X Elite host (server local):**

```bash
python3 agent.py "What is 12.5% of 840?"
python3 agent.py -v "What time is it, and what's 2^10?"   # -v shows THINK/ACT/OBSERVE
python3 agent.py                                          # interactive chat
```

### Profiles (skip retyping `--base-url` / `--model`)

Common settings live in `agent_profiles.json` as named presets. Pick one with
`--profile` instead of spelling out every flag:

```bash
python3 agent.py --list-profiles                 # show presets
python3 agent.py --profile cpu "What is 2^10?"   # llama.cpp on :8080
python3 agent.py --profile npu -v "What time is it?"   # Genie NPU on :8081 (compact prompt)
```

Profiles normally use `<device>-<cpu|npu>`. Additional runtime-specific profiles,
such as `iq8-aura-cpu`, preserve a validated preinstalled device configuration:

| Profile | Endpoint | Model | Notes |
|---|---|---|---|
| `xelite-cpu` | `:8080` | `gemma-4-E4B-it-Q4_K_M.gguf` | X Elite host, CPU |
| `xelite-npu` | `:8081` | `qwen3-4b-genie` | X Elite Hexagon NPU (HTP v73) |
| `iq9-cpu` | `:8080` | `gemma-4-12B-it-qat-UD-Q4_K_XL.gguf` | IQ9 QCS9075, CPU |
| `iq9-npu` | `:8081` | `qwen3-4b-instruct-2507-genie` | IQ9 NPU (reused X Elite bundle, `soc_model` 60→77) |
| `iq8-aura-cpu` | `:8080` | `/opt/aura-llm/qwen2.5-0.5b.gguf` | IQ8 QCS8275 preinstalled AURA CPU fast path; compact prompt |
| `iq8-cpu` | `:8080` | `gemma-4-E4B-it-Q4_K_M.gguf` | IQ8, CPU (tightest RAM ~11 GiB) |
| `iq8-npu` | `:8081` | `llama-3.2-1b-genie` | IQ8 (HTP v75) — **PENDING**, no bundle built yet |

The short aliases `cpu`, `npu`, and `iq9` are kept for backward compatibility
(`iq9` == `iq9-npu`). Precedence is **explicit flag > profile > env var >
built-in default**, so you can still override one value:
`--profile npu --max-steps 3`. Edit `agent_profiles.json` to add your own.

Run `agent.py` **with no prompt** (or pass `-i`/`--interactive`) to enter
interactive chat: it lets you pick a profile, lists the tools the agent can use,
then takes questions until `/exit`. Combine with `--profile` to skip the picker:
`python3 agent.py -i --profile npu`.

Interactive mode is a **loop-inspection view**: the `THINK → ACT → OBSERVE →
RESPOND` trace (plus a `[usage]` token summary) is **on by default**, so you
watch the agent reason step by step without passing `-v`. Slash-commands you can
type between questions:

| Command | Effect |
|---------|--------|
| `/verbose` (`/v`, `/trace`) | Toggle the THINK/ACT/OBSERVE trace on/off |
| `/tools` | Reprint the available tools |
| `/help` | List the commands |
| `/exit` (`/quit`) | Quit |

To really see it act like an agent (multi-step, chains several tools), give it a
goal that needs gathering before answering:

```bash
python3 agent.py -v "Profile this device: find the hostname, CPU architecture, \
number of cores, and total RAM. Then give me a one-line summary."
```

With `-v` you'll watch it plan and run `hostname`, then `lscpu`, then `free -h`,
then summarize — one reasoned step at a time.

**On the IQ8** — either run it on-device (server local, same command as above),
or drive the IQ8's server from your PC by pointing at its IP:

```bash
python3 agent.py --base-url http://<IQ8_IP>:8080 "Read /etc/hostname and tell me the device name."
```

That `--base-url` swap is the *only* difference between the two hosts.

## Run the agent in a Podman container

Same idea as the `--base-url` swap, one level up: build **one** arm64 image and
run it **unchanged** on the X Elite host, the IQ8, and the IQ9 (all aarch64
Linux); only `AGENT_BASE_URL` (or `--base-url`) changes per device. The image is
tiny — the agent is stdlib-only, so it's `python:slim` plus the agent sources,
no pip installs. The model is **not** baked in; the container still speaks HTTP
to a `llama.cpp` server you run separately.

```bash
cd projects/EdgeAgent
podman build -t edge-agent .
podman run --rm -it --network=host edge-agent -v "What is 12.5% of 840?"
```

Two things to know: **tools see the container, not the host** (`read_file` /
`run_shell` inspect the container's filesystem unless you mount host paths in),
and the **NPU/Genie path is not containerized** (`genie_server.py` drives the
Hexagon HTP, unreachable from inside a container — run it natively).

**→ Full container guide (host-networking, Podman-VM `host.containers.internal`,
mounting files, NPU-from-container): [`usage_podman.md`](usage_podman.md).**

## Coding mode (optional, opt-in)

By default the agent is **read-only** — it can inspect the device but not change
it. `--coding` adds file-editing tools so it can act like a (tiny) coding agent;
they're **sandboxed to a workspace dir** so the safety posture is preserved:

```bash
python3 agent.py --coding -v "Create hello.py that prints hi"          # write_file + apply_patch
python3 agent.py --coding --allow-exec -v "Write hello.py and run it"  # + run_command (asks y/N)
python3 agent.py --coding --workspace ./sandbox "..."                  # custom workspace
```

- **`write_file`** / **`apply_patch`** (with `--coding`) can only touch files
  **under the workspace** (default `./workspace`). Absolute paths and `..`
  traversal are refused; content is size-capped. `apply_patch` requires its
  `search` snippet to match **exactly once** (no ambiguous/whole-file clobber).
- **`run_command`** (with `--allow-exec`) runs a write-capable shell command in
  the workspace — but **pauses for `y/N` approval** before each one. There's no
  allowlist; the human is the gate.

> **This is a teaching extension, not a daily coding tool.** A 4B model on the
> NPU manages single-file, well-scoped edits but is weak at multi-file work
> (see the eval caveats). For real local coding, point a mature harness
> (Qwen-Code, Codex CLI, or the OpenAI SDK / LangChain) at `genie_server.py`'s
> `:8081` endpoint — see [`edge_agentic_ai.md`](edge_agentic_ai.md) §4. This mode
> exists to show *what a coding agent needs* (edit tools, a sandbox, an approval
> gate) and where a small model's limits are.

## Tools

| Tool | Args | Notes |
|------|------|-------|
| `calculator` | `{"expression": "2^10"}` | whitelisted to numbers and `+ - * / ^ ( ) .` (`^` = power) |
| `now` | `{}` | current local date/time |
| `sys_info` | `{}` | portable device profile (OS, arch, CPU count, Python, hostname) — same output on Windows host and Linux IQ8 |
| `read_file` | `{"path": "/etc/hostname"}` | small text files, truncated to 2000 chars |
| `list_dir` | `{"path": "."}` | directory listing (name, type, size), capped to 200 entries |
| `stat_file` | `{"path": "/etc/hostname"}` | path metadata (size, modified time, type) without reading contents |
| `run_shell` | `{"command": "free -h"}` | **read-only allowlist** — refuses anything whose first word isn't allowed, and refuses shell metacharacters (`; \| & > < \` $`) |

`sys_info`, `list_dir`, and `stat_file` are all **read-only and stdlib-only**, so
they run identically on the X Elite host and the IQ8. Prefer `sys_info` over
`run_shell` calls to `lscpu`/`free` for device profiling — those commands don't
exist on Windows, but `sys_info` works everywhere.

`run_shell` is what makes the agent feel powerful — it can inspect the device
(`ls`, `cat`, `uname`, `lscpu`, `free`, `df`, `ps`, `grep`, `find`, …) but
**cannot change anything**. The allowlist lives in `SHELL_ALLOWLIST` near the
top of `agent.py`; add to it deliberately.

Add a tool by writing a `tool_*(args) -> str` function and appending a
`Tool(name, summary, fn, args, example)` entry in `_build_registry()` in
`agent.py`. The `args`/`example` you give it drive both the generated system
prompt and a light arg-shape check — no other code needs to change.

## Running on the NPU (X Elite Hexagon HTP) via Genie

The CPU path above uses GGUF + llama.cpp. To run the LLM on the **X Elite NPU**
you use Qualcomm's **Genie** runtime instead — a different model format
(QNN context binaries). The agent itself does **not** change: `genie_server.py`
wraps the `genie-t2t-run` CLI in an OpenAI-compatible endpoint, and the agent
just points `--base-url` at it.

> Verified end-to-end with a fake `genie-t2t-run` stub (2026-06-17): agent →
> `genie_server.py` → CLI → agent works unmodified. Swap in the real binary and
> the agent is running on the NPU.

**Important:** the X Elite NPU is driven by the **Windows** QNN stack — do this
on **native ARM64 Windows (PowerShell)**, not WSL. WSL can't reach the Hexagon.

For the full copy/paste walkthrough — resolved paths, the required
`ADSP_LIBRARY_PATH`, the "run the server with CWD = bundle" gotcha, the `.bat`
shortcuts, and troubleshooting — see **[`usage.md`](usage.md)**.

### One-time setup (Windows PowerShell)

1. Install the **QAIRT SDK ≥ 2.29** (Qualcomm Software Center), then set env
   (X Elite = Hexagon **v73**):
   ```powershell
   $env:QAIRT_HOME = "C:\Qualcomm\AIStack\QAIRT\<version>"
   $env:Path = "$env:QAIRT_HOME\bin\aarch64-windows-msvc;" + $env:Path
   $env:Path = "$env:QAIRT_HOME\lib\aarch64-windows-msvc;" + $env:Path
   $env:ADSP_LIBRARY_PATH = "$env:QAIRT_HOME\lib\hexagon-v73\unsigned"
   ```
2. Export a Genie bundle for X Elite (runs on AI Hub cloud, **~2–3 h**, needs a
   qai-hub API token). This is the **Qwen3-4B-Instruct-2507** bundle the run
   step below uses — it's the one verified on this machine:
   ```powershell
   python -m venv llm_venv; .\llm_venv\Scripts\Activate.ps1
   pip install "qai-hub-models[qwen3-4b-instruct-2507]"
   python -m qai_hub_models.models.qwen3_4b_instruct_2507.export `
     --chipset qualcomm-snapdragon-x-elite --skip-profiling `
     --output-dir genie_bundle --context-length 2048
   ```
   The bundle ends up holding the HTP context binaries (`*_part_*_of_*.bin`),
   `tokenizer.json`, and `genie_config.json`. Other model families work too
   (e.g. `llama-v3-2-3b-instruct` — HF-gated, so `hf auth login` first); if you
   switch families, match `--chat-template` and `--model-name` in the run step
   below to the model you exported.

### Run it

The mechanics (ARM64 Python, the required `ADSP_LIBRARY_PATH`, running the shim
with **CWD = the bundle dir** so `tokenizer.json`/`*.bin` resolve, and the
`.bat` shortcuts) are all in **[`usage.md`](usage.md)**. In short: start the shim
in one terminal, then point the agent at it in another —

```powershell
python agent.py --base-url http://127.0.0.1:8081 --model qwen3-4b-genie -v "What is 2^10?"
```

`genie_server.py` flattens chat messages into the selected prompt format
(see `--chat-template`), invokes `genie-t2t-run`, parses the `[BEGIN]:…[END]`
output, and returns OpenAI JSON. See its `--help` for flags.

> NPU model ≠ CPU model. The CPU path runs a GGUF model via `llama.cpp`. The NPU
> path runs a **Genie bundle** (QNN context binaries) via QAIRT/Genie.

## Quick smoke check

```bash
python3 agent.py --help
```

## Standalone DevRel client features

This project includes the self-contained devrelAgent runtime under
`devrel_runtime/`; it does not import from any sibling project.
Create the dedicated Python 3.10 client/SDK environment and run the bundled CLI:

```powershell
.\setup_devrel_runtime.ps1
.\run_devrel_agent.ps1 --help
.\run_devrel_agent.ps1 detect --local-only
.\run_devrel_agent.ps1 doctor
```

Provisioning, transports, SDK access, hardware detection, device profiling,
UNO Q board operations, QNN helpers, bundled skills, tests, docs, tools, and
lightweight sample sources are included. See
[`DEVREL_STANDALONE.md`](DEVREL_STANDALONE.md) for setup, feature coverage, and the
local-only NPU policy.

## Evaluating the agent (`eval_agent.py`)

Leaderboard scores don't tell you if the agent works for *your* tasks. Following
the approach in Sebastian Raschka's *Using Local Coding Agents*, this project
ships a small, curated task set and a scorer that runs the **real** agent loop
against it — the local-agent equivalent of a unit-test suite. Re-run it on every
new model or backend to catch regressions.

```bash
# score the CPU (llama.cpp) backend
python3 eval_agent.py --base-url http://127.0.0.1:8080 --model gemma-4-E4B-it-Q4_K_M.gguf

# score the NPU (Genie) backend with the same tasks
python3 eval_agent.py --base-url http://127.0.0.1:8081 --model qwen3-4b-genie --compact-system-prompt
```

Tasks live in `eval_tasks.json`; each applies checks — `first_tool` (did it pick
the right tool?), `answer_contains` (did the final answer contain the expected
text?), `json_valid` (was the first reply parseable?). Output is `PASS`/`FAIL`
per task with a reason, a score, and token usage; exit code is non-zero on any
failure (so it drops into CI). Add your own workflow-representative tasks to the
JSON — no code changes needed.

> **Token accounting.** Run `agent.py -v` and the last line is a `[usage]`
> summary (steps + prompt/completion tokens). `llama.cpp` reports exact counts;
> `genie_server.py` doesn't, so those are estimated (~4 chars/token) and flagged
> `(estimated)`. Useful for seeing how much context a multi-step run really
> costs on a small device — and what `--max-history` saves.

## Flags

`--profile` (named preset), `--list-profiles`, `-i/--interactive`, `--base-url`
(server URL), `--model`, `--max-steps`, `--max-tokens`, `--temperature`,
`--timeout`, `--max-history`, `--compact-system-prompt`, `--coding`,
`--allow-exec`, `--workspace`, `-v/--verbose`. See `--help` for defaults.
