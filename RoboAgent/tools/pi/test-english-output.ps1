[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$pipeName = "roboagent_english_mock_$PID"
$logDirectory = Join-Path $root "logs\tests\english-$PID"
$mockOutput = Join-Path $logDirectory "mock.stdout.log"
$mockError = Join-Path $logDirectory "mock.stderr.log"
$piOutput = Join-Path $logDirectory "pi.stdout.log"
$piError = Join-Path $logDirectory "pi.stderr.log"
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
Remove-Item $mockOutput, $mockError, $piOutput, $piError -Force -ErrorAction SilentlyContinue

$env:ROBOAGENT_PIPE_NAME = $pipeName
$env:ROBOAGENT_WORKSPACE_ROOT = $root
$env:ROBOAGENT_CONTEXT_TOKENS = "3800"
$env:ROBOAGENT_HOST_SEQ_LEN = "3800"
$env:ROBOAGENT_MAX_TOKENS = "64"
$env:ROBOAGENT_ALLOW_HOST_RESTART = "0"
$env:ROBOAGENT_DEBUG_PROTOCOL = "0"
$env:ROBOAGENT_LOG_DIRECTORY = $logDirectory
$env:PI_OFFLINE = "1"

$mock = Start-Process node -WorkingDirectory $root -ArgumentList @((Join-Path $PSScriptRoot "mock-english-roboagent-host.mjs")) -RedirectStandardOutput $mockOutput -RedirectStandardError $mockError -PassThru

try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 100
        if ((Test-Path $mockOutput) -and (Select-String -LiteralPath $mockOutput -Pattern "MOCK_ENGLISH_LISTENING" -Quiet)) {
            $ready = $true
            break
        }
    }
    if (-not $ready) { throw "English-output mock host did not start." }

    $piScript = (Get-Command pi.ps1 -ErrorAction Stop).Source
    $pi = Start-Process powershell.exe -WorkingDirectory $root -PassThru -RedirectStandardOutput $piOutput -RedirectStandardError $piError -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $piScript,
        "-e", (Join-Path $PSScriptRoot "roboagent-gemma4.ts"),
        "--provider", "roboagent", "--model", "gemma4", "--no-tools", "--no-session", "--mode", "text",
        "-p", "Give a one-sentence explanation of an NPU."
    )
    if (-not $pi.WaitForExit(20000)) {
        throw "English-output test timed out waiting for Pi."
    }

    $output = ((Get-Content -LiteralPath $piOutput -Raw -ErrorAction SilentlyContinue) + (Get-Content -LiteralPath $piError -Raw -ErrorAction SilentlyContinue)).Trim()
    $pi.Refresh()
    $exitCode = $pi.ExitCode
    if ($null -ne $exitCode -and $exitCode -ne 0) { throw "English-output test Pi process failed with exit code $exitCode. $output" }
    if ($output -notmatch "The local model produced non-English text, so this response was suppressed") {
        throw "English-output test did not suppress the mocked foreign-language response. $output"
    }
    if ($output -match "[^\u0000-\u024f\u1e00-\u1eff\u2000-\u206f\u20a0-\u20cf]") {
        throw "English-output test displayed non-Latin text. $output"
    }
    Write-Output "ENGLISH_OUTPUT_TEST_PASSED"
}
finally {
    if ($mock -and -not $mock.HasExited) { Stop-Process -Id $mock.Id -Force -ErrorAction SilentlyContinue }
    if ($pi -and -not $pi.HasExited) { Stop-Process -Id $pi.Id -Force -ErrorAction SilentlyContinue }
}
