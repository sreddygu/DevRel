# DevRel Bring-up Agent

`devrel_agent.py` layers a read-only developer-onboarding workflow onto the
portable agent in `agent.py`. It uses only Python's standard library and the
existing local OpenAI-compatible model endpoint.

## Current scope

- Capture the developer goal, model, target, use case, and constraints.
- Detect local CPU, RAM, architecture, GPU, and Qualcomm hardware markers.
- Check Qualcomm SDK paths, command-line tools, DSP environment, Python version,
  and locally installed AI runtime packages.
- Check the loopback OpenAI-compatible model server and list its models.
- Select a candidate runtime based on model format and workload.
- Return structured `pass`, `warn`, `fail`, or `blocked` evidence.

Conversion, package installation, deployment, flashing, service exposure, and
arbitrary command execution are not exposed through the DevRel tools yet.

## Architecture

```text
devrel_agent.py
  -> agent.py model loop and safety controls
  -> devrel_tools.py workflow envelopes and tool routing
  -> devrel_local.py dependency-free local probes
     -> OS / CPU / RAM / architecture
     -> SDK variables and command discovery
     -> installed Python runtime discovery
     -> loopback /v1/models health check
```

The core DevRel agent remains standard-library-only and has no external cloud
model requirement. Full DevRel client features are available separately through
the bundled `devrel_runtime/` snapshot and dedicated `.venv_devrel`; see
`DEVREL_STANDALONE.md`. This keeps the small agent loop independent from the
optional `fastmcp`, `httpx`, and Typer client stack.

## Local-model policy

The DevRel entry point accepts only these model-server hosts:

- `127.0.0.1`
- `localhost`
- `::1`

A model running on another machine can still be used through an SSH tunnel bound
to loopback. Direct remote model URLs are rejected before the agent starts.

## Quick start

Run local probes without a model server:

```powershell
python -c "from devrel_tools import tool_devrel_hardware_detect; print(tool_devrel_hardware_detect({}))"
python -c "from devrel_tools import tool_devrel_doctor; print(tool_devrel_doctor({'real_mode': True}))"
```

Check the local model server:

```powershell
python -c "from devrel_tools import tool_devrel_model_server; print(tool_devrel_model_server({}))"
```

Run the agent against a local llama.cpp or Genie-compatible endpoint:

```powershell
python devrel_agent.py --profile cpu -v `
  "Assess this machine for Qualcomm NPU model bring-up."
```

Interactive mode:

```powershell
python devrel_agent.py -i --profile cpu
```

## Evaluation

```powershell
python eval_agent.py --toolset devrel --tasks devrel_eval_tasks.json `
  --profile cpu --temperature 0
```

The task set checks routing for intake, local hardware inspection, SDK/runtime
diagnostics, local model-server health, readiness assessment, and runtime
selection.

## Verified local runs

The following paths were exercised on August 6, 2026 on a Windows 11 ARM64
Snapdragon X Elite system with 12 CPU cores and approximately 32 GB RAM.

### CPU model server

Verified components:

- Server: `projects/LLM/llama.cpp-win-arm64/llama-server.exe`
- Model: `projects/LLM/models/gemma-4-E4B-it-Q4_K_M.gguf`
- Model size: approximately 4.98 GB
- Endpoint: `http://127.0.0.1:8080`
- Context size used during verification: 2048 tokens
- Threads: 8

Start the CPU server on loopback:

```powershell
# Run from projects/EdgeAgent.
$repoRoot = (Resolve-Path ..\..).Path
& "$repoRoot\projects\LLM\llama.cpp-win-arm64\llama-server.exe" `
  -m "$repoRoot\projects\LLM\models\gemma-4-E4B-it-Q4_K_M.gguf" `
  --host 127.0.0.1 --port 8080 --ctx-size 2048 --threads 8
```

Verify it:

```powershell
(Invoke-WebRequest -UseBasicParsing `
  -Uri "http://127.0.0.1:8080/v1/models").Content
```

Run the DevRel assessment:

```powershell
python devrel_agent.py --profile cpu --compact-system-prompt `
  --max-history 4 --max-steps 4 --max-tokens 512 -v `
  "Call devrel_assess with real_mode true. After the tool result, return a `
  NON-EMPTY concise final answer with exactly three sections: Blockers, `
  Evidence, Safest next step. Do not install or change anything."
```

Observed CPU result:

- Hardware detection passed and identified Snapdragon X Elite ARM64.
- Strict diagnostics failed when the QAIRT/QNN environment was not exported to
  the agent process.
- Missing items included a configured SDK root, QNN command-line tools on
  `PATH`, and `ADSP_LIBRARY_PATH`.
- The first verbose multi-tool run exceeded the 2048-token context at 2105
  tokens. `--compact-system-prompt --max-history 4` resolved this.
- A 256-token completion sometimes produced an empty final `answer`. Increasing
  `--max-tokens` to 512 and explicitly requesting a non-empty concise response
  produced a complete answer.

CPU server logs used during verification:

- `llama-server.stdout.log`
- `llama-server.stderr.log`

### NPU direct sanity test

Verified components:

- QAIRT: `C:\Qualcomm\AIStack\QAIRT\2.51.40.260930`
- Genie binary: `bin\aarch64-windows-msvc\genie-t2t-run.exe`
- DSP libraries: `lib\hexagon-v73\unsigned`
- Bundle: `C:\genie_bundle\qwen3_4b_instruct_2507-genie-w4a16-qualcomm_snapdragon_x_elite`
- Bundle model: Qwen3-4B-Instruct-2507, W4A16
- Context length: 2048
- Bundle split: four QNN context binaries

Run the direct NPU test before starting the HTTP shim:

```powershell
& .\start_npu_genie.bat test
```

The direct test successfully reported:

- `QnnHtp.dll` as the backend library.
- DSP architecture `73` and SoC model `60`.
- A real QNN device connection with status `0x0`.
- Eight loaded QNN graphs: prompt and token graphs split across four context
  binaries.
- Successful QNN backend, device, context, graph, and shared-buffer setup.
- Successful cleanup with exit status zero.

This direct test is the primary evidence that the bundle executes through the
Hexagon HTP rather than merely exposing an HTTP endpoint.

### NPU model server

The supplied `start_npu_genie.bat` defaults to `127.0.0.1`. The equivalent
explicit local-only setup is:

```powershell
$edgeRoot = (Get-Location).Path
$qairt = "C:\Qualcomm\AIStack\QAIRT\2.51.40.260930"
$bundle = "C:\genie_bundle\qwen3_4b_instruct_2507-genie-w4a16-qualcomm_snapdragon_x_elite"

$env:QAIRT_HOME = $qairt
$env:Path = "$qairt\bin\aarch64-windows-msvc;" +
  "$qairt\lib\aarch64-windows-msvc;" + $env:Path
$env:ADSP_LIBRARY_PATH = "$qairt\lib\hexagon-v73\unsigned"

Push-Location $bundle
& "$edgeRoot\.venv\Scripts\python.exe" `
  "$edgeRoot\genie_server.py" `
  --config ".\genie_config.json" `
  --binary "$qairt\bin\aarch64-windows-msvc\genie-t2t-run.exe" `
  --chat-template qwen `
  --model-name qwen3-4b-genie `
  --host 127.0.0.1 --port 8081 --timeout 300
Pop-Location
```

Verify model discovery:

```powershell
(Invoke-WebRequest -UseBasicParsing `
  -Uri "http://127.0.0.1:8081/v1/models").Content
```

Expected model ID:

```text
qwen3-4b-genie
```

Verified completion request:

```powershell
$body = @{
  model = "qwen3-4b-genie"
  messages = @(@{role = "user"; content = "Reply with exactly: NPU_OK"})
  max_tokens = 32
  temperature = 0
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8081/v1/chat/completions" `
  -Method Post -ContentType "application/json" -Body $body `
  -TimeoutSec 300
```

The verified response content was `NPU_OK`.

NPU server logs:

- `genie-server.stdout.log`
- `genie-server.stderr.log`

### DevRel agent using the NPU model

Run the agent with the QAIRT environment visible to both the model server and
the local diagnostics:

```powershell
$qairt = "C:\Qualcomm\AIStack\QAIRT\2.51.40.260930"
$env:QAIRT_HOME = $qairt
$env:Path = "$qairt\bin\aarch64-windows-msvc;" +
  "$qairt\lib\aarch64-windows-msvc;" + $env:Path
$env:ADSP_LIBRARY_PATH = "$qairt\lib\hexagon-v73\unsigned"

.\.venv\Scripts\python.exe devrel_agent.py `
  --profile npu --compact-system-prompt `
  --max-history 4 --max-steps 4 --max-tokens 512 -v `
  "MANDATORY: Your first response must call the devrel_assess tool with `
  real_mode=true and base_url=http://127.0.0.1:8081. Do not answer before `
  receiving the tool result. Then return a non-empty concise answer with `
  Blockers, Evidence, and Safest next step."
```

Observed NPU-agent result:

- The first unconstrained attempt answered directly without calling a tool and
  incorrectly claimed there were no blockers. Do not trust a readiness claim
  unless the trace contains an `ACT: devrel_assess(...)` and an `OBSERVE` row.
- The mandatory-tool prompt correctly called `devrel_assess`.
- Hardware detection identified Windows 11 ARM64, Snapdragon X Elite, Adreno
  GPU, 12 CPU cores, and approximately 32 GB RAM.
- The local model-server check passed and found `qwen3-4b-genie` on port 8081.
- The Agents `.venv` uses Python 3.13.7. The diagnostic marked this as a warning
  because common Qualcomm NPU Python packages target Python 3.10 through 3.12.
- `torch`, `onnxruntime`, `executorch`, `qai_hub`, and `qai_hub_models` were not
  installed in the lightweight Agents environment. These packages are not
  required by the stdlib HTTP shim, but they are relevant for conversion and
  Python-runtime workflows.

The model ID alone is not proof of NPU execution. Treat the successful direct
`genie-t2t-run` HTP test plus the successful `NPU_OK` completion as the combined
evidence for this verified NPU path.

### Recommended operating split

- Keep the Agents runtime lightweight and stdlib-only.
- Run `genie_server.py` in the existing Agents environment; it does not require
  the Python NPU packages.
- Use a separate native ARM64 Python 3.10-3.12 environment for ONNX Runtime QNN,
  ExecuTorch, AI Hub, conversion, and profiling workflows.
- Always export the QAIRT `bin`, `lib`, and `ADSP_LIBRARY_PATH` values in the
  process that performs NPU work.
- Keep both model endpoints bound to loopback unless remote access is explicitly
  required and secured.

### Stop the local servers

List the processes before stopping them:

```powershell
Get-Process llama-server, python -ErrorAction SilentlyContinue |
  Select-Object Id, ProcessName, Path
```

Stop only the verified server process IDs:

```powershell
Stop-Process -Id <llama-server-pid>
Stop-Process -Id <genie-server-python-pid>
```

Do not stop every Python process on the machine.

## Next milestone

Add approval-gated local actions for environment provisioning, conversion,
deployment, runtime launch, output validation, and profiling. Each action should
include rollback instructions and artifact manifests.
