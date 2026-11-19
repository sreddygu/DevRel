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

- [Mojo / MAX](https://docs.modular.com/mojo/manual/get-started) (`uv add mojo` or `magic add max`)
- Python 3.10+
- For on-device runs: SSH access to IQ9/IQ8, QAIRT runtime deployed

## Quick Start (host)

```bash
uv init
uv add mojo max
uv run mojo run hello.mojo
```

## Quick Start (IQ9)

```bash
# Install Mojo on device (ARM64 Linux)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv init && uv add mojo
uv run mojo run hello.mojo
```

For NPU inference, Mojo connects to the Genie service via IPC.  
See `../../EdgeAgent/genie_server.py` and `../../EdgeAgent/start_iq9_genie.sh`.

## Related Projects

- `../EdgeAgent` — Genie server, agent loop, IQ9/IQ8 bring-up scripts
- `../LLM` — GGUF + llama.cpp path (CPU inference)
