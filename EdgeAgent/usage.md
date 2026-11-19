# Usage (CPU via llama.cpp, or NPU via Genie)

> Bring-up detail for `agent.py`. For the project overview, the model rationale,
> and the tool list, see [`README.md`](README.md); to run the agent in a
> container, see [`usage_podman.md`](usage_podman.md).

This documents how to run `agent.py` in two modes:
- **CPU (normal)**: against a local `llama.cpp` server (OpenAI-compatible HTTP).
- **NPU (X Elite)**: against a local `genie_server.py` shim that drives QAIRT/Genie on Hexagon HTP.

Assumptions:
- You are on **Windows ARM64** (Snapdragon X Elite host).
- You have a working **QAIRT** install that includes `genie-t2t-run.exe`.
- You have a compiled Genie bundle folder containing `genie_config.json`, `tokenizer.json`, and `*_part_*_of_*.bin`.
- Your current directory is the repository's `projects\EdgeAgent` folder.

## CPU (normal) via llama.cpp

Optional convenience script (Windows):
- `.\start_cpu_llama.bat`

### 1) Start `llama-server.exe` (Terminal 1)

Start an OpenAI-compatible server on `http://127.0.0.1:8080` (example):

```powershell
$projectsRoot = (Resolve-Path ..).Path
& "$projectsRoot\LLM\llama.cpp-win-arm64\llama-server.exe" `
  -m "$projectsRoot\LLM\models\gemma-4-E4B-it-Q4_K_M.gguf" `
  --host 127.0.0.1 --port 8080 --ctx-size 2048 --threads 8
```

Health check:

```powershell
curl.exe -s http://127.0.0.1:8080/v1/models
```

### 2) Run the agent (Terminal 2)

```powershell
.\.venv\Scripts\Activate.ps1
python .\agent.py -v "What is 12.5% of 840?"
```

If your server is not on `:8080`, point the agent at it:

```powershell
python .\agent.py --base-url http://127.0.0.1:8080 -v "What is 12.5% of 840?"
```

## Resolved paths (this machine)

```powershell
$QAIRT_HOME = "C:\Qualcomm\AIStack\QAIRT\2.47.1.260610"
# The bundle MUST live on a plain local disk, NOT under C:\Dropbox -- see the
# mmap gotcha in Troubleshooting. We keep a working copy here:
$BUNDLE_DIR = "C:\genie_bundle\qwen3_4b_instruct_2507-genie-w4a16-qualcomm_snapdragon_x_elite"
$GENIE_T2T_RUN = "$QAIRT_HOME\bin\aarch64-windows-msvc\genie-t2t-run.exe"
```

> **Shortcut — just use the batch file.** Pasting these long paths into
> PowerShell is error-prone (line-wrap corruption). `start_npu_genie.bat` in this
> folder hard-codes everything below and has two modes:
> - `.\start_npu_genie.bat test` — direct NPU sanity check (step 3 below), no HTTP.
> - `.\start_npu_genie.bat` — starts the `genie_server.py` shim on `127.0.0.1:8081`
>   (step 4 below), ready for the agent or the Podman container.
>
> Edit the `set` lines at the top (or set the matching env vars) if paths change.

## NPU (X Elite) via Genie

Convenience script (Windows): `.\start_npu_genie.bat` (add `test` for a direct
NPU sanity check without the HTTP shim).

## 1) Use an ARM64 Python

Use the project venv by default:

```powershell
.\.venv\Scripts\Activate.ps1
```

Confirm you’re running native ARM64 Python:

```powershell
python -c "import platform; print(platform.machine())"
```

It should print `ARM64`.

## 2) One-time environment setup (PowerShell session)

Genie/QNN needs `ADSP_LIBRARY_PATH` so it can load the Hexagon skels.

```powershell
$env:QAIRT_HOME = $QAIRT_HOME
$env:Path = "$QAIRT_HOME\bin\aarch64-windows-msvc;$QAIRT_HOME\lib\aarch64-windows-msvc;" + $env:Path
$env:ADSP_LIBRARY_PATH = "$QAIRT_HOME\lib\hexagon-v73\unsigned"
```

Sanity-check DSP prerequisites (optional but recommended):

```powershell
qnn-platform-validator.exe --backend dsp --testBackend --debug
```

## 3) (Optional) Run the bundle directly (no HTTP)

Run from inside the bundle folder so relative paths (like `tokenizer.json`) resolve:

```powershell
Push-Location $BUNDLE_DIR
& $GENIE_T2T_RUN -c .\genie_config.json --prompt_file .\sample_prompt.txt --log info
Pop-Location
```

## 4) Start the OpenAI shim (Terminal 1)

Important: run `genie_server.py` with **working directory = the bundle folder** so `tokenizer.json` and the `*.bin` parts resolve.

```powershell
Push-Location $BUNDLE_DIR
python genie_server.py `
  --config .\genie_config.json `
  --binary $GENIE_T2T_RUN `
  --chat-template qwen `
  --model-name qwen3-4b-genie `
  --host 127.0.0.1 --port 8081 `
  --timeout 300
Pop-Location
```

Quick health check:

```powershell
curl.exe -s http://127.0.0.1:8081/v1/models
```

## 5) Run the agent on the NPU (Terminal 2)

From the EdgeAgent directory:

```powershell
python .\agent.py --base-url http://127.0.0.1:8081 --model qwen3-4b-genie -v "What is 2^10?"
```

Tip: Genie bundles are often compiled with a smaller context window (e.g. 2048). If the agent hits a
`Context Size was exceeded` error, re-run with:

```powershell
python .\agent.py --compact-system-prompt --base-url http://127.0.0.1:8081 --model qwen3-4b-genie -v "What is 2^10?"
```

## 6) Compare CPU vs NPU (latency / throughput)

This only makes sense if you have **both** servers running:
- CPU: `llama-server` on `http://127.0.0.1:8080`
- NPU: `genie_server.py` on `http://127.0.0.1:8081`

Then run:

```powershell
.\benchmark_cpu_vs_npu.ps1 -Iterations 3 -Prompt "Give a 1-sentence summary of what an NPU is."
```

Notes:
- **Model quality may differ**: CPU and NPU typically run different model files/formats.
- The main “advantage” of NPU is usually **CPU offload / efficiency** (and leaving CPU free), not necessarily lower latency for short prompts.

## Troubleshooting

### `Failed to load skel` / `qnn_open failed 0x80000406`
You’re missing `ADSP_LIBRARY_PATH` (or it points to the wrong Hexagon version).

```powershell
$env:ADSP_LIBRARY_PATH = "$QAIRT_HOME\lib\hexagon-v73\unsigned"
```

### HTTP 500 with `Failed to open input file: tokenizer.json` (or missing `*.bin`)
`genie_server.py` is launching `genie-t2t-run` from the wrong working directory.

Fix: start the server with `Push-Location $BUNDLE_DIR` (or otherwise set CWD to the bundle dir), and keep `genie_config.json` relative references intact.

### `Received path to an empty file ... Nothing to deserialize` (bundle under Dropbox)
`genie-t2t-run` reports the `.bin` context binaries as **empty and fails to load
the model** — even though the files are fully present on disk (full size, readable
by `type`/`head`, no "offline"/placeholder attribute).

Cause: `genie_config.json` sets `"use-mmap": true`, so Genie **memory-maps** the
weight files. **Dropbox's filesystem filter driver blocks memory-mapping** of
files inside its synced tree (`C:\Dropbox\...`). Ordinary reads succeed, so the
files *look* fine — but the mmap sees an empty stream. (The same driver also
makes `Copy-Item` of those `.bin` files fail with "Access denied", while `cp` /
`robocopy` streaming reads still work.)

Fix: keep the bundle on a **plain local disk**, not under Dropbox. Copy it out
once and point `$BUNDLE_DIR` (and the `.bat` files) at the copy:

```powershell
$projectsRoot = (Resolve-Path ..).Path
robocopy `
  "$projectsRoot\LLM\genie_bundle\qwen3_4b_instruct_2507-genie-w4a16-qualcomm_snapdragon_x_elite" `
  "C:\genie_bundle\qwen3_4b_instruct_2507-genie-w4a16-qualcomm_snapdragon_x_elite" /E
```

Re-copy after any re-export. `start_npu_genie.bat` refuses to run against a
`C:\Dropbox` path for this reason.
