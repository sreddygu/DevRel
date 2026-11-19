[CmdletBinding()]
param(
    [string]$PipeName = "gemma4",
    [int]$SeqLen = 3800,
    [int]$StartupTimeoutSeconds = 45
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$sdk = $env:QNN_SDK_ROOT
if (-not $sdk) { $sdk = "C:\Qualcomm\AIStack\QAIRT\2.47.1.260610" }

$env:QNN_SDK_ROOT = $sdk
$env:Path = "$root\RelWithDebInfo;$sdk\lib\aarch64-windows-msvc;$env:Path"
$env:ADSP_LIBRARY_PATH = "$sdk\lib\hexagon-v73\unsigned"
$env:ROBOAGENT_PIPE_NAME = $PipeName

$runtimeDirectory = Join-Path $root ".roboagent-runtime"
$logDirectory = $env:ROBOAGENT_LOG_DIRECTORY
if (-not $logDirectory) { $logDirectory = Join-Path $root "logs" }
$stdout = Join-Path $logDirectory "host.stdout.log"
$stderr = Join-Path $logDirectory "host.stderr.log"
$readyFile = Join-Path $runtimeDirectory "host-ready-$PipeName.txt"
$recoveryLog = Join-Path $logDirectory "host-recovery-$PipeName.log"
New-Item -ItemType Directory -Force -Path $runtimeDirectory | Out-Null
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
Remove-Item $readyFile, $recoveryLog -Force -ErrorAction SilentlyContinue

function Write-RecoveryStatus {
    param([Parameter(Mandatory = $true)][string]$Message)
    Add-Content -LiteralPath $recoveryLog -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff') $Message"
}

function Test-RoboAgentPipe {
    param([Parameter(Mandatory = $true)][string]$Name)
    $client = $null
    try {
        $client = New-Object System.IO.Pipes.NamedPipeClientStream(".", $Name, [System.IO.Pipes.PipeDirection]::InOut)
        $client.Connect(1000)
        return $true
    } catch {
        return $false
    } finally {
        if ($client) { $client.Dispose() }
    }
}

$existingHosts = @(Get-Process qnn_llm_host -ErrorAction SilentlyContinue)
if ($existingHosts.Count -gt 0) {
    Write-RecoveryStatus "Stopping existing RoboAgent host process(es): $($existingHosts.Id -join ', ')."
    $existingHosts | Stop-Process -Force
    $deadline = (Get-Date).AddSeconds(10)
    do {
        Start-Sleep -Milliseconds 100
        $remainingHosts = @(Get-Process qnn_llm_host -ErrorAction SilentlyContinue)
    } while ($remainingHosts.Count -gt 0 -and (Get-Date) -lt $deadline)

    if ($remainingHosts.Count -gt 0) {
        Write-RecoveryStatus "Timed out waiting for the previous RoboAgent host to exit."
        throw "Timed out waiting for the previous RoboAgent host to exit before context recovery."
    }
}

$modelDir = Join-Path $root "models\gemma4_e2b_sc8380xp_ctxt_4000_ar_l-128"
$lastFailure = $null

for ($startAttempt = 1; $startAttempt -le 2; $startAttempt++) {
    Remove-Item $stdout, $stderr, $readyFile -Force -ErrorAction SilentlyContinue
    Write-RecoveryStatus "Starting RoboAgent host recovery attempt $startAttempt of 2."
    $process = Start-Process (Join-Path $root "qnn_llm_host.exe") -WorkingDirectory $logDirectory -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr -ArgumentList @(
        "--model_path", (Join-Path $modelDir "gemma4_e2b_sc8380xp_ctxt_4000-001.pte"),
        "--tokenizer_path", (Join-Path $modelDir "tokenizer.json"),
        "--decoder_model_version", "gemma4",
        "--pipe_name", $PipeName,
        "--seq_len", $SeqLen
    )

    for ($attempt = 0; $attempt -lt ($StartupTimeoutSeconds * 2); $attempt++) {
        Start-Sleep -Milliseconds 500
        if ((Test-Path $stderr) -and (Select-String -LiteralPath $stderr -Pattern "Listening on" -Quiet) -and (Test-RoboAgentPipe -Name $PipeName)) {
            Set-Content -LiteralPath $readyFile -Value "ready" -NoNewline
            Write-RecoveryStatus "RoboAgent host is listening and the named pipe probe succeeded."
            exit 0
        }
        if ($process.HasExited) {
            $logTail = if (Test-Path $stderr) { (Get-Content $stderr -Tail 12) -join "`n" } else { "No host stderr log was written." }
            $lastFailure = "RoboAgent host exited during context recovery attempt $startAttempt. Recent host log:`n$logTail"
            Write-RecoveryStatus "RoboAgent host exited during recovery attempt $startAttempt."
            break
        }
    }

    if (-not $process.HasExited) {
        $process | Stop-Process -Force -ErrorAction SilentlyContinue
        $lastFailure = "Timed out waiting for RoboAgent host recovery attempt $startAttempt."
        Write-RecoveryStatus "Timed out waiting for recovery attempt $startAttempt after $StartupTimeoutSeconds seconds."
    }
    if ($startAttempt -lt 2) { Start-Sleep -Seconds 1 }
}

Write-RecoveryStatus "RoboAgent host recovery failed after two attempts."
throw "RoboAgent host failed to recover after two attempts. $lastFailure"
