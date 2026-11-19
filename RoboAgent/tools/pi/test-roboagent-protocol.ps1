[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$pipeName = "roboagent_pi_mock_$PID"
$logDirectory = Join-Path $root "logs\tests\protocol-$PID"
$stdout = Join-Path $logDirectory "mock.stdout.log"
$stderr = Join-Path $logDirectory "mock.stderr.log"
$trace = Join-Path $logDirectory "pi-protocol.jsonl"
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "node.exe" -and $_.CommandLine -match "roboagent-gemma4\.ts|mock-roboagent-host\.mjs"
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Remove-Item $stdout, $stderr, $trace -Force -ErrorAction SilentlyContinue

$env:ROBOAGENT_PIPE_NAME = $pipeName
$env:ROBOAGENT_READ_ONLY_TOOLS = "1"
$env:ROBOAGENT_WORKSPACE_ROOT = $root
$env:ROBOAGENT_DEBUG_PROTOCOL = "1"
$env:ROBOAGENT_LOG_DIRECTORY = $logDirectory
$env:PI_OFFLINE = "1"
$env:ROBOAGENT_CONTEXT_TOKENS = "3800"
$env:ROBOAGENT_ALLOW_HOST_RESTART = "1"
$pi = $null
$mock = Start-Process node -WorkingDirectory $root -ArgumentList @((Join-Path $PSScriptRoot "mock-roboagent-host.mjs")) -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru

try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 100
        if ((Test-Path $stdout) -and (Select-String -LiteralPath $stdout -Pattern "MOCK_LISTENING" -Quiet)) { $ready = $true; break }
    }
    if (-not $ready) { throw "Mock RoboAgent host did not start." }

    $piOutput = Join-Path $logDirectory "mock-pi.out"
    $piError = Join-Path $logDirectory "mock-pi.err"
    Remove-Item $piOutput, $piError -Force -ErrorAction SilentlyContinue
    $piScript = (Get-Command pi.ps1 -ErrorAction Stop).Source
    $pi = Start-Process powershell.exe -WorkingDirectory $root -PassThru -RedirectStandardOutput $piOutput -RedirectStandardError $piError -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $piScript, "-e", (Join-Path $PSScriptRoot "roboagent-gemma4.ts"), "--provider", "roboagent", "--model", "gemma4", "--no-builtin-tools", "--tools", "read_file", "--no-session", "--mode", "text", "-p", "Read README.md and report the required RoboAgent environment variables.")
    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    do {
        Start-Sleep -Milliseconds 250
        $events = if (Test-Path $trace) { @(Get-Content $trace | ForEach-Object { $_ | ConvertFrom-Json }) } else { @() }
        $finalEvents = @($events | Where-Object { $_.direction -eq "final" })
    } while ($finalEvents.Count -eq 0 -and [DateTime]::UtcNow -lt $deadline)
    if ($finalEvents.Count -eq 0) {
        $diagnostics = ((Get-Content $piOutput -Raw -ErrorAction SilentlyContinue) + (Get-Content $piError -Raw -ErrorAction SilentlyContinue)).Trim()
        throw "Protocol test timed out waiting for a final trace event. $diagnostics"
    }
    $output = [string]$finalEvents[-1].text
    Write-Output $output
    if ($output -notmatch "QNN_SDK_ROOT" -or $output -notmatch "ADSP_LIBRARY_PATH") { throw "Protocol test did not produce the expected final answer." }
    $firstFinalIndex = [array]::IndexOf($events, $finalEvents[0])
    $completedExchange = @($events[0..$firstFinalIndex])
    if (@($completedExchange | Where-Object { $_.direction -eq "tool_call" -and $_.status -eq "valid" }).Count -ne 1) { throw "Protocol test did not record exactly one valid tool request." }
    if (@($completedExchange | Where-Object { $_.direction -eq "final" -and $_.grounded -eq $true }).Count -ne 1) { throw "Protocol test did not record a grounded final answer." }
    Write-Output "PROTOCOL_TEST_PASSED"
}
finally {
    Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq "node.exe" -and $_.CommandLine -match "roboagent-gemma4\.ts"
    } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    if ($mock -and -not $mock.HasExited) { Stop-Process -Id $mock.Id -Force -ErrorAction SilentlyContinue }
}
