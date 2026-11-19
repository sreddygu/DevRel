param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$DevRelArgs
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv_devrel\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Missing .venv_devrel. Run .\setup_devrel_runtime.ps1 first."
}

& $Python (Join-Path $Root "devrel_client.py") @DevRelArgs
exit $LASTEXITCODE
