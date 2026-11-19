#Requires -Version 5.1
<#
.SYNOPSIS
    Dependency bootstrap helper -- installs all required packages via uv.

.DESCRIPTION
    Creates a local .venv and installs every package listed in
    requirements.txt using uv.  Run this once before running the app.

    Pass -Python to target a specific interpreter (default: 3.10).

.EXAMPLE
    # One-time setup
    .\run.ps1

    # Run against the IQ-9075 over adb (serial auto-detected if only one board attached)
    .venv\Scripts\python.exe run_iq9075.py

    # Skip re-pushing artifacts if already on the board
    .venv\Scripts\python.exe run_iq9075.py --skip-push

    # More benchmark runs for stable KPI numbers
    .venv\Scripts\python.exe run_iq9075.py --iterations 50

    # Skip the (currently blocked) NPU/GPU attempt entirely
    .venv\Scripts\python.exe run_iq9075.py --cpu-only
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

# 1. Verify requirements.txt exists
if (-not (Test-Path $ReqFile)) {
    Write-Error "requirements.txt not found: $ReqFile"
    exit 1
}

# 2. Verify uv -- auto-install if missing
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Info "uv not found -- installing ..."
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    # Refresh PATH so uv is visible in this session
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","User") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH","Machine")
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Error "uv install failed. Install manually: https://docs.astral.sh/uv/"
        exit 1
    }
}
Write-Ok "uv $(uv --version)"

# 3. Create venv if absent
if (-not (Test-Path $VenvDir)) {
    Write-Info "Creating .venv (Python $Python) ..."
    uv venv "$VenvDir" --python $Python
    if ($LASTEXITCODE -ne 0) { Write-Error "uv venv failed."; exit 1 }
    Write-Ok ".venv created"
} else {
    Write-Ok ".venv already exists -- skipping creation"
}

# 4. Install dependencies
Write-Info "Installing dependencies from requirements.txt ..."
uv pip install --system-certs --python "$VenvDir\Scripts\python.exe" -r "$ReqFile"
if ($LASTEXITCODE -ne 0) { Write-Error "uv pip install failed."; exit 1 }
Write-Ok "All dependencies installed"

Write-Host ""
Write-Host "  Setup complete.  Run the benchmark:" -ForegroundColor Cyan
Write-Host ""
Write-Host "    .venv\Scripts\python.exe run_iq9075.py              # full run (adb push + on-device inference)"
Write-Host "    .venv\Scripts\python.exe run_iq9075.py --skip-push  # reuse artifacts already on the board"
Write-Host ""
Write-Host "  NOTE: NPU/GPU are currently blocked on this board -- see README.md" -ForegroundColor Yellow
Write-Host "  'Known limitations'. CPU results are real; NPU/GPU report the exact reason." -ForegroundColor Yellow
Write-Host ""
