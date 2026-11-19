param(
    [switch]$WithSamples,
    [switch]$WithNpuPython,
    [switch]$Refresh,
    [switch]$TrustedPypi
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv = Join-Path $Root ".venv_devrel"
$Python = Join-Path $Venv "Scripts\python.exe"
$NpuVenv = Join-Path $Root ".venv_devrel_npu"
$NpuPython = Join-Path $NpuVenv "Scripts\python.exe"
$CreatedClientVenv = $false
$CreatedNpuVenv = $false

function Invoke-Checked {
    param(
        [string]$FilePath,
        [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments
    )
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

function Install-Requirements {
    param(
        [string]$Interpreter,
        [string]$Requirements
    )
    $PipArgs = @("-m", "pip", "install")
    if ($TrustedPypi) {
        $PipArgs += @(
            "--timeout", "120",
            "--retries", "5",
            "--trusted-host", "pypi.org",
            "--trusted-host", "files.pythonhosted.org"
        )
    }
    $PipArgs += @("-r", $Requirements)
    Invoke-Checked $Interpreter @PipArgs
}

if (-not (Test-Path $Python)) {
    $Launcher = Get-Command py -ErrorAction SilentlyContinue
    if (-not $Launcher) {
        throw "Python launcher 'py' was not found. Install Python 3.10-3.12."
    }

    Invoke-Checked py -3.10 -m venv $Venv
    $CreatedClientVenv = $true
}

if ($CreatedClientVenv -or $Refresh) {
    Install-Requirements $Python (Join-Path $Root "requirements-devrel.txt")
}

if ($WithSamples -and ($CreatedClientVenv -or $Refresh)) {
    Install-Requirements $Python (Join-Path $Root "requirements-devrel-samples.txt")
}

if ($WithNpuPython) {
    if (-not (Test-Path $NpuPython)) {
        Invoke-Checked py -3.12-arm64 -m venv $NpuVenv
        $CreatedNpuVenv = $true
    }
    if ($CreatedNpuVenv -or $Refresh) {
        Install-Requirements $NpuPython (Join-Path $Root "requirements-devrel-npu.txt")
    }
}

Invoke-Checked $Python -c "import typer, httpx, fastmcp; print('DevRel client dependencies: OK')"
if ($WithSamples) {
    Invoke-Checked $Python -c "import numpy, PIL, onnxruntime, scipy, tqdm; print('DevRel sample dependencies: OK')"
}
if ($WithNpuPython) {
    Invoke-Checked $NpuPython -c "import os, onnxruntime as ort, onnxruntime_qnn, onnxruntime_genai, qai_hub; path=onnxruntime_qnn.get_library_path(); assert os.path.exists(path); ort.register_execution_provider_library('QNNExecutionProvider', path); assert 'QNNExecutionProvider' in ort.get_available_providers(); print('DevRel ARM64 NPU dependencies: OK')"
}
Invoke-Checked $Python (Join-Path $Root "devrel_client.py") --help

Write-Host "Standalone DevRel runtime is ready in $Venv"
if ($WithNpuPython) {
    Write-Host "Optional ARM64 NPU Python runtime is ready in $NpuVenv"
}
