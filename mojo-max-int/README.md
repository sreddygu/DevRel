# mojo-max-int

Run a Mojo application and a MAX Graph inference pipeline on Qualcomm IQ hardware.

Mojo runs on the ARM CPU for application logic.  
MAX executes the model graph on CPU (and, where supported, GPU/NPU via the appropriate backend).

## What's Here

- Notebook: `notebooks/mojo_max_intro.ipynb`

## Targets

| Device | CPU | Accelerator |
|--------|-----|-------------|
| IQ9 (QCS9075) | ARM64 (8-core) | Hexagon V73 NPU |
| IQ8 (QCS8275) | ARM64 | Hexagon V75 NPU |
| X Elite (host dev) | ARM64 Oryon | GPU (via MAX) |

## Prerequisites

- [Mojo / MAX](https://docs.modular.com/mojo/manual/get-started) (`uv add mojo==0.26.1 max==26.1.0`; newer Mojo releases such as 1.x reject `fn` and need source updates)
- Python 3.10+
- For on-device runs: SSH access to IQ9/IQ8, QAIRT runtime deployed

## Quick Start (host)

```bash
uv init
uv add mojo==0.26.1 max==26.1.0
uv run mojo run src/hello.mojo
uv run mojo run -I src src/agent.mojo -- --help   # agent needs -I src to find genie_client
```

## Quick Start (IQ9)

```bash
# Install Mojo on device (ARM64 Linux)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv init && uv add mojo==0.26.1
uv run mojo run src/hello.mojo
```

For NPU inference, Mojo connects to the Genie service via IPC.  
See `../../EdgeAgent/genie_server.py` and `../../EdgeAgent/start_iq9_genie.sh`.

## Related Projects

- `../EdgeAgent` — Genie server, agent loop, IQ9/IQ8 bring-up scripts
- `../LLM` — GGUF + llama.cpp path (CPU inference)

## Verification status (2026-11-27)

Run under WSL (aarch64 Ubuntu on a Windows-on-Snapdragon PC) with Mojo 0.26.1 and MAX 26.1.0:

- `src/hello.mojo` runs.
- `src/agent.mojo` and `src/genie_client.mojo` compile and run against an OpenAI-shaped stub server
  (one tool call dispatched, one final answer). Piped stdin ends with "EOF when reading a line" because
  the agent has no EOF handling.
- `src/max_graph_demo.mojo` does **not** compile on any Mojo/MAX release: the MAX Python-interop API it
  uses has changed (`with Graph(...)` blocks, `max.driver.Tensor` is now `Buffer`). The same two graphs
  (matmul and ReLU) run in current MAX Python on aarch64 CPU; porting the Mojo file is still open.
- Not run: a real Genie server (needs an IQ9 bundle) and the notebook.
