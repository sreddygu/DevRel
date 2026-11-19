---
name: quad-run-ps1
description: Use when the user asks to "add a run script", "create run.ps1", "set up dependencies for this app", or invokes /quad-run-ps1. Also apply automatically whenever creating or scaffolding any new QUAD application or sample.
trigger: "run-ps1"
---

# QUAD run.ps1 Convention

Every QUAD application directory **must** ship two files alongside the
application code:

| File | Purpose |
|------|---------|
| `requirements.txt` | All Python dependencies, one per line with `>=` version pins |
| `run.ps1` | Generic dependency installer — creates `.venv` via uv and installs `requirements.txt` |

`run.ps1` is **not** application-specific. It does not hard-code any
script name, model path, or argument. Its sole job is environment setup.
The user runs the application separately after calling `run.ps1`.

---

## Canonical run.ps1 template

Copy this verbatim. Replace only the synopsis and the Python version if
the application requires something other than 3.10.

```powershell
#Requires -Version 5.1
<#
.SYNOPSIS
    Dependency bootstrap helper — installs all required packages via uv.

.DESCRIPTION
    Creates a local .venv and installs every package listed in
    requirements.txt using uv.  Run this once before running the app.

    Pass -Python to target a specific interpreter (default: 3.10).

.EXAMPLE
    .\run.ps1
    .\run.ps1 -Python 3.11
#>

[CmdletBinding()]
param(
    [string]$Python = "3.10"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Ok($msg)   { Write-Host "  [OK]    $msg" -ForegroundColor Green }
function Write-Info($msg) { Write-Host "  [INFO]  $msg" }

$ReqFile = Join-Path $PSScriptRoot "requirements.txt"
$VenvDir = Join-Path $PSScriptRoot ".venv"

if (-not (Test-Path $ReqFile)) {
    Write-Error "requirements.txt not found: $ReqFile"
    exit 1
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Info "uv not found -- installing ..."
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","User") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH","Machine")
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Error "uv install failed. Install manually: https://docs.astral.sh/uv/"
        exit 1
    }
}
Write-Ok "uv $(uv --version)"

if (-not (Test-Path $VenvDir)) {
    Write-Info "Creating .venv (Python $Python) ..."
    uv venv "$VenvDir" --python $Python
    if ($LASTEXITCODE -ne 0) { Write-Error "uv venv failed."; exit 1 }
    Write-Ok ".venv created"
} else {
    Write-Ok ".venv already exists -- skipping creation"
}

Write-Info "Installing dependencies from requirements.txt ..."
uv pip install --system-certs --python "$VenvDir\Scripts\python.exe" -r "$ReqFile"
if ($LASTEXITCODE -ne 0) { Write-Error "uv pip install failed."; exit 1 }
Write-Ok "All dependencies installed"
```

---

## requirements.txt rules

- Pin with `>=` minimum versions, not `==` exact pins (allows users to
  upgrade without breaking)
- Group related deps with inline comments
- Always include the packages the main script actually imports at the top
  level; do not omit transitive deps that the user must install manually
- **NPU / Snapdragon apps:** include the AI Hub Models + NPU runtime wheels.
  `onnxruntime-genai` is ONE package (no `-qnn` variant exists) — its
  win-arm64 wheel carries the Hexagon support, so it needs no per-arch
  split. `onnxruntime-qnn` (the ONNX Execution Provider for embeddings) IS
  arm64-only, so pair it with a commented CPU `onnxruntime` fallback. For
  the full provisioning flow (token + native-arm64-Python detection +
  install), defer to the `quad-npu-prereqs` skill — it writes these lines
  and installs them. NPU runtime apps also need an **arch-aware `run.ps1`**
  (see note below).

Example:
```
fastmcp>=2.0
numpy>=1.24
Pillow>=10.0
onnx>=1.14                 # model loading/saving
onnxsim>=0.4.35            # QAIRT converter compatibility

# AI Hub Models + on-device NPU LLM (one package; win-arm64 wheel = NPU, else CPU)
qai-hub
qai-hub-models
onnxruntime-genai          # NPU LLM decode (NOT onnxruntime-genai-qnn — no such pkg)

# NPU embeddings EP (arm64-only); CPU fallback for x86 dev hosts
onnxruntime-qnn>=1.17.0    # X-Elite Hexagon ONNX Execution Provider
# onnxruntime>=1.18        # x86 fallback (use instead of onnxruntime-qnn)
```

**Arch-aware `run.ps1` for NPU runtime apps.** On a Snapdragon X-Elite the
runtime venv MUST use native arm64 Python — an emulated x86 Python (Prism)
reports `machine()=AMD64` and the arm64-only NPU wheels won't install or
reach the NPU. The `run.ps1` for any NPU app should: detect arm64 silicon,
scan `%LOCALAPPDATA%\Programs\Python` for a `python.exe` whose
`platform.machine()` is `ARM64`, create the venv from it, and **recreate a
wrong-arch existing venv** (venv only — never touch system Python). Copy
SAGE's `run.ps1` (`sewa-apps/SAGE/run.ps1`) verbatim for this.

---

## When to apply

Apply this skill (create or verify both files exist) whenever you:

- Create a new sample in `samples/`
- Generate application code via `quad-codegen`
- Scaffold any standalone Python script that uses QUAD tools
- Add a new `examples/` entry

If `run.ps1` or `requirements.txt` already exist, update them rather
than replacing them — preserve existing entries.
