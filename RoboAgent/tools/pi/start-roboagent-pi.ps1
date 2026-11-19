[CmdletBinding()]
param(
    [string]$ModelProfile = "gemma4",
    [string]$PipeName,
    [int]$SeqLen = 0,
    [switch]$NoTools,
    [switch]$ReadOnlyTools,
    [switch]$EnableMutations,
    [switch]$KeepHostRunning,
    [string]$Prompt,
    [switch]$NoSession,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PiArguments
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
. (Join-Path $PSScriptRoot "roboagent-model-profiles.ps1")
$model = Get-RoboAgentModelProfile -Name $ModelProfile -Root $root
if (-not $PipeName) { $PipeName = $model.PipeName }
if ($SeqLen -le 0) { $SeqLen = $model.DefaultSeqLen }
if ($SeqLen -gt $model.ContextTokens) { throw "SeqLen $SeqLen exceeds the $($model.ContextTokens)-token context limit for profile '$ModelProfile'." }
$mutationsEnabled = $EnableMutations -or $env:ROBOAGENT_ENABLE_MUTATIONS -eq "1"
if ($mutationsEnabled -and ($NoTools -or -not $ReadOnlyTools)) {
    throw "Enable mutations with -ReadOnlyTools -EnableMutations. Mutation tools cannot run without the read-only tool set."
}
$sdk = $env:QNN_SDK_ROOT
if (-not $sdk) { $sdk = "C:\Qualcomm\AIStack\QAIRT\2.47.1.260610" }

$env:QNN_SDK_ROOT = $sdk
$env:Path = "$root\RelWithDebInfo;$sdk\lib\aarch64-windows-msvc;$env:Path"
$env:ADSP_LIBRARY_PATH = "$sdk\lib\hexagon-v73\unsigned"
$env:ROBOAGENT_PIPE_NAME = $PipeName
$env:ROBOAGENT_WORKSPACE_ROOT = $root
$env:ROBOAGENT_MODEL_ID = $model.PiModelId
$env:ROBOAGENT_MODEL_NAME = $model.DisplayName
$env:ROBOAGENT_CONTEXT_TOKENS = $model.ContextTokens
$env:ROBOAGENT_PI_CONTEXT_TOKENS = $model.PiContextTokens
$env:ROBOAGENT_HOST_SEQ_LEN = $SeqLen
$env:ROBOAGENT_MAX_TOKENS = $model.MaxTokens
$env:PI_OFFLINE = "1"
$env:ROBOAGENT_READ_ONLY_TOOLS = if ($ReadOnlyTools -and -not $NoTools) { "1" } else { "0" }
$env:ROBOAGENT_ENABLE_MUTATIONS = if ($mutationsEnabled) { "1" } else { "0" }
$env:ROBOAGENT_ALLOW_HOST_RESTART = "1"
$env:ROBOAGENT_DEBUG_PROTOCOL = "1"

function Test-RoboAgentPipe {
    param([Parameter(Mandatory = $true)][string]$Name)

    $client = $null
    try {
        $client = New-Object System.IO.Pipes.NamedPipeClientStream(".", $Name, [System.IO.Pipes.PipeDirection]::InOut)
        $client.Connect(250)
        return $true
    } catch {
        return $false
    } finally {
        if ($client) { $client.Dispose() }
    }
}

$hostProcess = Get-Process qnn_llm_host -ErrorAction SilentlyContinue | Select-Object -First 1
$startedHost = $false
$logDirectory = $env:ROBOAGENT_LOG_DIRECTORY
if (-not $logDirectory) { $logDirectory = Join-Path $root "logs" }
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$env:ROBOAGENT_LOG_DIRECTORY = $logDirectory

try {
    if (-not $hostProcess) {
        $stdout = Join-Path $logDirectory "host.stdout.log"
        $stderr = Join-Path $logDirectory "host.stderr.log"
        Remove-Item $stdout, $stderr -Force -ErrorAction SilentlyContinue
        $hostProcess = Start-Process (Join-Path $root "qnn_llm_host.exe") -WorkingDirectory $logDirectory -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr -ArgumentList @(
            "--model_path", $model.ModelPath,
            "--tokenizer_path", $model.TokenizerPath,
            "--decoder_model_version", $model.DecoderModelVersion,
            "--pipe_name", $PipeName,
            "--seq_len", $SeqLen
        )
        $startedHost = $true
    }

    $ready = $false
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        Start-Sleep -Milliseconds 500
        $log = Join-Path $logDirectory "host.stderr.log"
        if ((Test-Path $log) -and (Select-String -Path $log -Pattern "Listening on" -Quiet) -and (Test-RoboAgentPipe -Name $PipeName)) { $ready = $true; break }
        if ($hostProcess.HasExited) { throw "RoboAgent host exited before opening the named pipe." }
    }
    if (-not $ready) { throw "Timed out waiting for \\.\pipe\$PipeName." }

    $extension = Join-Path $PSScriptRoot "roboagent-gemma4.ts"
    $arguments = @("-e", $extension, "--provider", "roboagent", "--model", $model.PiModelId)
    if ($NoTools -or -not $ReadOnlyTools) {
        $arguments += "--no-tools"
    } else {
        $arguments += "--no-builtin-tools"
        $arguments += @("--tools", "read_file,list_directory,search_files,get_git_status,get_git_diff")
    }
    if ($mutationsEnabled) {
        $arguments += @("--tools", "read_file,list_directory,search_files,get_git_status,get_git_diff,write_file,apply_patch,run_command")
    }
    if ($Prompt) { $arguments += @("-p", $Prompt) }
    if ($NoSession) { $arguments += "--no-session" }
    $arguments += $PiArguments
    & pi @arguments
}
finally {
    if ($startedHost -and -not $KeepHostRunning -and $hostProcess -and -not $hostProcess.HasExited) {
        try {
            $client = New-Object System.IO.Pipes.NamedPipeClientStream(".", $PipeName, [System.IO.Pipes.PipeDirection]::InOut)
            $client.Connect(2000)
            $writer = New-Object System.IO.StreamWriter($client)
            $writer.AutoFlush = $true
            $reader = New-Object System.IO.StreamReader($client)
            $writer.WriteLine('{"cmd":"shutdown"}')
            [void]$reader.ReadLine()
            $client.Dispose()
        } catch { }
        for ($attempt = 0; $attempt -lt 10 -and -not $hostProcess.HasExited; $attempt++) {
            Start-Sleep -Milliseconds 200
        }
        if (-not $hostProcess.HasExited) {
            Stop-Process -Id $hostProcess.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
