# Generic uv-based dependency installer for this DevRel sample.
# Creates a local .venv with Python 3.10 and installs requirements.txt.
# The user runs the application separately:
#
#     .\run.ps1
#     .venv\Scripts\python.exe build_model.py
#     .venv\Scripts\python.exe generate.py
#     .venv\Scripts\python.exe -m pytest tests/ -q

$ErrorActionPreference = "Stop"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv not found on PATH. Install from https://docs.astral.sh/uv/ first." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path ".venv")) {
    Write-Host "Creating .venv with Python 3.10..." -ForegroundColor Cyan
    uv venv --python 3.10 .venv
}

Write-Host "Installing dependencies from requirements.txt..." -ForegroundColor Cyan
uv pip install --system-certs --python .venv\Scripts\python.exe -r requirements.txt

# DevRel core is needed by generate.py to call generate_code(). Installed
# editable from the sibling DevRel checkout.
$coreRoot = Resolve-Path "..\..\..\DevRel" -ErrorAction SilentlyContinue
if ($coreRoot) {
    Write-Host "Installing DevRel core (editable) from $coreRoot..." -ForegroundColor Cyan
    uv pip install --system-certs --python .venv\Scripts\python.exe -e $coreRoot
} else {
    Write-Host "WARN: DevRel core checkout not found at ..\..\..\DevRel -- generate.py will fail until it is installed." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done. Next steps:" -ForegroundColor Green
Write-Host "  .venv\Scripts\python.exe build_model.py"
Write-Host "  .venv\Scripts\python.exe generate.py"
Write-Host "  .venv\Scripts\python.exe -m pytest tests/ -q"
