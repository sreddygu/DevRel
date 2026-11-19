# PyTorch → ExecuTorch `.pte` on Snapdragon, via QUAD

One script that takes a **PyTorch** model all the way to an on-device
**ExecuTorch `.pte`** through the QUAD MCP server — export + lower to the
Qualcomm (QNN) delegate, profile per-op, allocate across CPU/GPU/NPU, and
generate runner code.

```
samples/executorch_mobilenet/
├── run_executorch.py   — convert → profile → orchestrate → codegen (all-in-one)
├── requirements.txt    — Python dependencies (just fastmcp for mock mode)
├── run.ps1             — uv-based dependency installer
└── README.md           — this file
```

---

## Quick start

```powershell
# one-time: install sample dependencies
.\run.ps1

# mock end-to-end (works on ANY machine — no torch, no NPU, no QNN SDK)
.venv\Scripts\python.exe run_executorch.py
```

On macOS / Linux:

```bash
pip install -r requirements.txt
python run_executorch.py
```

The script:

1. **hardware_detect** — identifies the target chipset + NPU.
2. **convert_model** — exports the PyTorch model to a `.pte` with the
   `qnn-htp` delegate (`target_sdk="executorch"`), and prints the **delegate
   partition map**: how many ops run on the NPU vs fall back to CPU.
3. **profile_workload** — per-op ETDump-style profile of the `.pte`.
4. **orchestrate_workload** — the CPU/GPU/NPU split the partition implies.
5. **generate_code** — emits an ExecuTorch runner (`generated/`).

A real stub `.pte` is written to disk, and the generated runner lands in
`generated/`.

---

## What "mock mode" means here

By default the sample runs the QUAD server in **mock mode**, so it works
everywhere and is fully deterministic. The `.pte` is a stub QUAD writes
directly; the partition map and per-op profile are realistic simulations. This
is the same mock-first model every QUAD capability ships with.

## Going real

```powershell
.venv\Scripts\python.exe run_executorch.py --real --platform android
```

A real export needs a **build-capable host**:

| Requirement | Why |
|-------------|-----|
| Python 3.10–3.13 | ExecuTorch is `requires-python <3.14` |
| `torch` + `executorch` | the export + lowering toolchain (`pip install executorch torch`) |
| QUAD's QAIRT SDK (`QAIRT_SDK_ROOT`) | the QNN delegate builds + runs against it |
| `quad doctor` → **ExecuTorch SDK** green | confirms the above |

If the host isn't ready, the server's real adapter returns a precise
"missing prerequisite" message — the sample prints it verbatim.

---

## Options

| Flag | Default | Choices |
|------|---------|---------|
| `--platform` | `android` | windows / linux / android / gateway / robotics |
| `--runtime` | `qnn-htp` | qnn-htp / qnn-gpu / xnnpack / vulkan / arm |
| `--quantization` | `int8` | fp32 / int8 / fp16 |
| `--language` | `python` | python / cpp |
| `--power-mode` | `performance` | performance / balanced / efficiency |
| `--real` | off | drive the real export on a build-capable host |
| `--model` | `mobilenet_v2.pt` | path to your PyTorch model |

Try `--runtime xnnpack` first if you have no NPU/QAIRT — it validates the
export + `.pte` end to end on CPU.

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.10+ | `python --version` |
| QUAD server installed | Clone [QUAD](https://github.com/CBN-AI-TEAM/QUAD) in a sibling dir and run `install.ps1` / `install.sh` |
| fastmcp | installed by `run.ps1` / `requirements.txt` |

The sample auto-spawns the QUAD MCP server as a subprocess — there's no server
to start manually.
