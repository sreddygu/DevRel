# Standalone devrelAgent

The `EdgeAgent` directory contains the complete devrelAgent implementation and its
local runtime. No sibling source tree is required.

## Environments

- `.venv`: lightweight local agent and Genie HTTP adapter.
- `.venv_devrel`: Python 3.10 x64 client, SDK, transports, tests, and samples.
- `.venv_devrel_npu`: Python 3.12 ARM64 QNN, GenAI, and AI Hub packages.

Create or validate them:

```powershell
.\setup_devrel_runtime.ps1
.\setup_devrel_runtime.ps1 -WithSamples -WithNpuPython
```

Existing environments are validated without package-index access. Use
`-Refresh` to reinstall dependencies. On a TLS-intercepting network, the
explicit `-TrustedPypi` option enables the two required package hosts.

## Commands

```powershell
.\run_devrel_agent.ps1 --help
.\run_devrel_agent.ps1 detect --local-only
.\run_devrel_agent.ps1 doctor
.\run_devrel_agent.ps1 status --project-root .
.\run_devrel_agent.ps1 preview --transport stdio-local
.\run_devrel_agent.ps1 unoq --help
```

## Included Features

- Claude Code and opencode provisioning.
- Local, SSH stdio, and HTTP/SSE transport probes.
- Python MCP client SDK.
- Hardware detection, diagnostics, and device profiles.
- UNO Q board lifecycle and diagnostic operations.
- QNN and ONNX Runtime QNN helpers.
- Bundled skills, tests, docs, tools, and lightweight samples.

Remote transports and physical-board operations remain available only when the
user explicitly supplies a host or endpoint. Local diagnostics and local model
inference do not require them.

## Local NPU

```powershell
$env:GENIE_HOST = "127.0.0.1"
.\start_npu_genie.bat

.\.venv\Scripts\python.exe devrel_agent.py --profile npu `
  "Call devrel_model_server and summarize the local NPU endpoint."
```

The native Genie path uses QAIRT directly. The ARM64 Python environment also
registers `QNNExecutionProvider` for ONNX Runtime workflows.
