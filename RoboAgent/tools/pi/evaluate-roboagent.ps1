[CmdletBinding()]
param(
    [string]$PipeName = "gemma4",
    [string]$OutputPath = "logs\evaluation-results.jsonl",
    [int]$TimeoutSeconds = 120
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$launcher = Join-Path $PSScriptRoot "start-roboagent-pi.ps1"
$outputFile = Join-Path $root $OutputPath
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outputFile) | Out-Null
Remove-Item $outputFile -Force -ErrorAction SilentlyContinue
$logDirectory = Join-Path $root "logs\evaluation"
$env:ROBOAGENT_LOG_DIRECTORY = $logDirectory
$traceFile = Join-Path $logDirectory "pi-protocol.jsonl"
Get-Process qnn_llm_host -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
$tasks = @(
    @{ Name = "explain-host"; Prompt = "Read cpp/qnn_llm_host.cpp and explain its role in this project."; NoTools = $false },
    @{ Name = "read-readme"; Prompt = "Read README.md and extract the three QNN environment variables required to start the host."; NoTools = $false },
    @{ Name = "search-pipe"; Prompt = "Use search_files with path cpp/qnn_llm_host.cpp to find the text Listening on, then report the source location."; NoTools = $false },
    @{ Name = "git-status"; Prompt = "Inspect the Git status and summarize whether this workspace has uncommitted changes. Do not modify anything."; NoTools = $false }
)

foreach ($task in $tasks) {
    Write-Host "`n=== $($task.Name) ===" -ForegroundColor Cyan
    Remove-Item $traceFile -Force -ErrorAction SilentlyContinue
    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    $taskPipeName = "gemma4_eval_${PID}_$($task.Name -replace '-', '_')"
    $arguments = @("-PipeName", $taskPipeName, "-Prompt", $task.Prompt, "-NoSession")
    if ($task.NoTools) { $arguments = @("-NoTools") + $arguments }
    else { $arguments = @("-ReadOnlyTools") + $arguments }
    $taskOutput = Join-Path $logDirectory "$($task.Name).out"
    $taskError = Join-Path $logDirectory "$($task.Name).err"
    Remove-Item $taskOutput, $taskError -Force -ErrorAction SilentlyContinue
    $childArguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $launcher) + $arguments
    $argumentLine = ($childArguments | ForEach-Object {
        if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' }
        else { $_ }
    }) -join ' '
    $process = Start-Process powershell.exe -WorkingDirectory $root -PassThru -RedirectStandardOutput $taskOutput -RedirectStandardError $taskError -ArgumentList $argumentLine
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $trace = @()
    $finalEvents = @()
    do {
        Start-Sleep -Milliseconds 250
        if (Test-Path $traceFile) {
            $trace = @(Get-Content -LiteralPath $traceFile | ForEach-Object { try { $_ | ConvertFrom-Json } catch { } })
            $finalEvents = @($trace | Where-Object { $_.direction -eq "final" })
        }
    } while ($finalEvents.Count -eq 0 -and -not $process.HasExited -and [DateTime]::UtcNow -lt $deadline)
    if ($finalEvents.Count -gt 0) {
        $answer = [string]$finalEvents[0].text
        $exitCode = 0
    } elseif (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        $answer = "Evaluation timed out after $TimeoutSeconds seconds."
        $exitCode = 124
    } else {
        $process.WaitForExit()
        $process.Refresh()
        $answer = ((Get-Content $taskOutput -Raw -ErrorAction SilentlyContinue) + (Get-Content $taskError -Raw -ErrorAction SilentlyContinue)).Trim()
        $exitCode = [int]$process.ExitCode
    }
    if ($finalEvents.Count -gt 0 -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq "node.exe" -and $_.CommandLine -match "roboagent-gemma4\.ts"
    } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Get-Process qnn_llm_host -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    $timer.Stop()
    $firstFinalIndex = if ($finalEvents.Count -gt 0) { [array]::IndexOf($trace, $finalEvents[0]) } else { $trace.Count - 1 }
    $completedExchange = if ($firstFinalIndex -ge 0) { @($trace[0..$firstFinalIndex]) } else { @() }
    $toolEvents = @($completedExchange | Where-Object { $_.direction -eq "tool_call" })
    $expectedEvidence = switch ($task.Name) {
        "explain-host" { "qnn_llm_host.cpp" }
        "read-readme" { "QNN_SDK_ROOT" }
        "search-pipe" { "cpp/qnn_llm_host.cpp" }
        "git-status" { "Git" }
    }
    $record = [ordered]@{
        task = $task.Name
        elapsed_ms = $timer.ElapsedMilliseconds
        exit_code = $exitCode
        tool_requested = ($toolEvents.Count -gt 0)
        valid_tool_request = (@($toolEvents | Where-Object { $_.status -eq "valid" }).Count -gt 0)
        repeated_tool_request = (@($toolEvents | Where-Object { $_.status -eq "repeated" }).Count -gt 0)
        malformed_or_unknown_tool_request = (@($toolEvents | Where-Object { $_.status -eq "invalid" }).Count -gt 0)
        grounded_final_answer = if ($finalEvents.Count -gt 0) { [bool]$finalEvents[0].grounded } else { $answer -match [regex]::Escape($expectedEvidence) }
        expected_evidence = $expectedEvidence
        tool_request_reason = (($toolEvents | ForEach-Object { $_.reason } | Where-Object { $_ }) -join "; ")
        answer = $answer
    }
    ($record | ConvertTo-Json -Compress) | Add-Content -LiteralPath $outputFile
    Write-Host $answer
    if ($exitCode -ne 0) { throw "Evaluation task failed with exit code $exitCode." }
}

Write-Host "`nResults written to $outputFile" -ForegroundColor Green
