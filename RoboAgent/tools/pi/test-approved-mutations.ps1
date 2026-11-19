[CmdletBinding()]
param(
    [string]$FixturePath = ".roboagent-runtime\mutation-fixture.txt"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$fixture = Join-Path $root $FixturePath
$fixtureDirectory = Split-Path -Parent $fixture
New-Item -ItemType Directory -Force -Path $fixtureDirectory | Out-Null
Set-Content -Path $fixture -Value "phase=initial" -NoNewline

Write-Host "Disposable mutation fixture: $FixturePath" -ForegroundColor Cyan
Write-Host "Pi allows one validated tool call per exchange. Enter these prompts one at a time and approve only the matching request:" -ForegroundColor Yellow
Write-Host "1. Use write_file to overwrite $FixturePath with exactly phase=written."
Write-Host "2. Use apply_patch to replace exactly phase=written with phase=patched in $FixturePath."
Write-Host "3. Use run_command to execute exactly: Get-Content $FixturePath"
Write-Host "After the third result, type exit. This script then verifies phase=patched." -ForegroundColor Yellow

& (Join-Path $PSScriptRoot "start-roboagent-pi.ps1") -ReadOnlyTools -EnableMutations

$content = Get-Content -Path $fixture -Raw
if ($content -ne "phase=patched") {
    throw "Mutation validation did not complete. Expected phase=patched; found: $content"
}

Write-Host "APPROVED_MUTATION_TEST_PASSED" -ForegroundColor Green
