# devrelAgent Local Architecture

`EdgeAgent` is a self-contained local project. It does not import source code,
configuration, skills, or environments from any sibling project.

## Components

- `devrel_agent.py`: local LLM-driven onboarding and diagnostic agent.
- `devrel_client.py`: standalone developer tooling CLI entry point.
- `devrel_runtime/`: bundled client SDK, transports, hardware probes, board
  operations, skills, tests, docs, tools, and sample source.
- `.venv_devrel`: Python 3.10 x64 environment for client, SDK, and tooling.
- `.venv_devrel_npu`: Python 3.12 ARM64 environment for QNN Python runtimes.
- `genie_server.py`: loopback OpenAI-compatible adapter for native Genie NPU
  inference.

## Local-Only Defaults

- Model endpoints use `127.0.0.1`.
- `start_npu_genie.bat` defaults to `GENIE_HOST=127.0.0.1`.
- `devrel_agent.py` rejects non-loopback model URLs.
- `devrel_targets.json` contains only local endpoints.
- Remote transports and board commands are explicit CLI actions; they are never
  selected automatically by the local agent.

## Start

```powershell
.\setup_devrel_runtime.ps1 -WithSamples -WithNpuPython
.\run_devrel_agent.ps1 detect --local-only
.\run_devrel_agent.ps1 doctor
```

Start local NPU inference separately:

```powershell
$env:GENIE_HOST = "127.0.0.1"
.\start_npu_genie.bat
```

Then run the local agent:

```powershell
.\.venv\Scripts\python.exe devrel_agent.py --profile npu `
  "Call devrel_model_server and summarize the local NPU endpoint."
```
