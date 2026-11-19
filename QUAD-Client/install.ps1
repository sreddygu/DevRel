# ==========================================================================
# QUAD-Client -- Windows installer (PowerShell)
#
# Verifies Python + Git Bash, then delegates to install.sh.
#
# Usage:
#   .\install.ps1                                  # interactive
#   .\install.ps1 -Transport stdio-ssh -SshUser alice -SshHost lab.lan
#   .\install.ps1 -Transport sse-http -SseUrl https://mcp.example.com/sse
# ==========================================================================
param(
    # NB: deliberately NO [ValidateSet] on -Transport / -Agent. A Unix-style
    # flag like `--agent opencode` binds `--agent` positionally to -Transport;
    # a ValidateSet would reject it during *parameter binding* with a cryptic
    # framework error before our friendly hint below can run. We validate these
    # in the body instead, after first trapping leaked `--flags`.
    [string]$Transport = "",
    [string]$SshUser = "",
    [string]$SshHost = "",
    [int]$SshPort = 22,
    [string]$SshKey = "",
    [string]$SseUrl = "",
    [string]$SseAuthTokenEnv = "",
    [switch]$Force,
    [switch]$SkipTest,
    [switch]$FromPyPI,
    [string]$Agent = "",
    [switch]$NoLaunch,
    # Catch-all for tokens PowerShell could not bind to a named parameter.
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Leftover = @()
)

$ErrorActionPreference = "Stop"

function Write-Section($msg) { Write-Host ""; Write-Host "=== $msg ===" -ForegroundColor Cyan; Write-Host "" }
function Write-Ok($msg)      { Write-Host "  [OK]    $msg" -ForegroundColor Green }
function Write-Info($msg)    { Write-Host "  [INFO]  $msg" }
function Write-Err($msg)     { Write-Host "  [ERROR] $msg" -ForegroundColor Red }

# Map a Unix-style `--some-flag` to its PowerShell `-SomeFlag` equivalent.
function ConvertTo-PsFlagHint($tok) {
    $bare = ($tok -replace '^-+', '') -replace '=.*$', ''   # strip dashes + =value
    $pascal = ($bare -split '-' | ForEach-Object {
        if ($_.Length -gt 0) { $_.Substring(0,1).ToUpper() + $_.Substring(1) }
    }) -join ''
    return "-$pascal"
}

Write-Section "QUAD-Client installer"

# --- Reject stray / Unix-style arguments ----------------------------------
# install.ps1 is a PowerShell script: flags are single-dash (-Agent), not
# double-dash (--agent). A user copying a bash invocation would have
# `--agent opencode` bound positionally to -Transport/-SshUser. Detect any
# `--flag` that leaked into a string parameter or the catch-all, and reject
# with a precise "did you mean -Foo?" hint instead of running with garbage.
$strayTokens = @()
foreach ($v in @($Transport, $SshUser, $SshHost, $SshKey, $SseUrl, $SseAuthTokenEnv, $Agent)) {
    if ($v -like '--*') { $strayTokens += $v }
}
$strayTokens += @($Leftover | Where-Object { $_ -like '--*' })
if ($strayTokens.Count -gt 0) {
    Write-Err "Unrecognized Unix-style argument(s): $($strayTokens -join ' ')"
    foreach ($tok in $strayTokens) {
        Write-Err "  '$tok' looks like a Unix-style flag. Did you mean '$(ConvertTo-PsFlagHint $tok)'?"
    }
    Write-Err "This is a PowerShell script -- use single-dash flags (e.g. -Agent opencode)."
    Write-Err "Run 'Get-Help .\install.ps1' for the full list."
    exit 2
}
if ($Leftover.Count -gt 0) {
    Write-Err "Unrecognized argument(s): $($Leftover -join ' ')"
    Write-Err "Run 'Get-Help .\install.ps1' for valid options."
    exit 2
}

# --- Validate enumerated options (now that no stray --flags remain) -------
$validTransports = @("", "stdio-local", "stdio-ssh", "sse-http")
if ($validTransports -notcontains $Transport) {
    Write-Err "Invalid -Transport '$Transport'. Valid: stdio-local, stdio-ssh, sse-http."
    exit 2
}
$validAgents = @("", "claude", "opencode", "codex")
if ($validAgents -notcontains $Agent) {
    Write-Err "Invalid -Agent '$Agent'. Valid: claude, opencode, codex."
    exit 2
}

# --- Python ---------------------------------------------------------------
# Honor $env:PYTHON if the developer set it deliberately (e.g. they have 3.14 as
# the default on PATH but pointed us at a supported 3.12). Only fall back to PATH
# resolution when $env:PYTHON is unset. Without this, the version gate below runs
# against whatever `python` resolves to first on PATH and rejects it, throwing
# away the developer's explicit choice (IQ9 issue 25).
if ($env:PYTHON -and (Test-Path $env:PYTHON)) {
    $pythonExe = $env:PYTHON
    Write-Ok "Using `$env:PYTHON = $pythonExe"
} else {
    if ($env:PYTHON) {
        Write-Warn "`$env:PYTHON is set to '$env:PYTHON' but that path does not exist - falling back to PATH."
    }
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        Write-Err "Python not found on PATH."
        Write-Err "Install Python 3.10+ from https://www.python.org/downloads/ and ensure 'python' is on PATH."
        Write-Err "Or set `$env:PYTHON to the full path of a supported (3.10-3.12) python.exe and re-run."
        exit 1
    }
    $pythonExe = $pythonCmd.Source
}
$pyVersion = (& $pythonExe --version 2>&1).ToString().Trim()
Write-Ok $pyVersion

# Python version gate: onnxruntime-qnn / onnxruntime-genai NPU wheels are built
# only for 3.10–3.12. 3.13+ (a normal "latest Python") installs fine here but
# NPU support later fails with a cryptic wheel error, so fail fast with a clear
# message instead (IQ-9075 retrospective issue 1).
if ($pyVersion -match "Python\s+(\d+)\.(\d+)") {
    $pyMajor = [int]$Matches[1]
    $pyMinor = [int]$Matches[2]
    if ($pyMajor -eq 3 -and ($pyMinor -lt 10 -or $pyMinor -gt 12)) {
        Write-Err "$pyVersion is not supported - please use Python 3.10 to 3.12."
        Write-Err "The onnxruntime-qnn NPU wheels are not built for 3.13+, so NPU support"
        Write-Err "would fail to install. Set `$env:PYTHON to the full path of a 3.10-3.12 interpreter and re-run."
        exit 1
    }
}

# Forward the interpreter we just validated to install.sh. Without this,
# install.sh defaults to `python3` (PYTHON="${PYTHON:-python3}"), which on
# Windows is usually the Microsoft Store alias stub — it prints nothing, so
# install.sh fails with "Could not parse 'Python X.Y.Z' from 'python3 --version'".
# Pass the FULL resolved path (not the bare name) so Git Bash uses the exact
# binary PowerShell validated rather than re-resolving PATH itself. We already
# honored an existing $env:PYTHON above; set it now if it was resolved via PATH.
if (-not $env:PYTHON) {
    $env:PYTHON = $pythonExe
    Write-Ok "Using interpreter: $pythonExe"
}

# --- Native ARM64 Python advisory (Snapdragon X Elite) --------------------
# QUAD-Client itself is transport-agnostic and works fine on emulated x86
# Python — but if the user installs the QUAD *server* on this same box the
# host-side qairt-converter will fail with libDlModelToolsPy ImportError.
# Surface the warning and offer to install ARM64 Python via winget so the
# server side works without a second debug round.
$cpuArch = (Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Architecture)
if ($cpuArch -eq 12) {  # ARM64 host
    $pyArch = (& $pythonExe -c "import sysconfig; print(sysconfig.get_platform())" 2>$null)
    if ($pyArch -and ($pyArch -match "amd64|x86")) {
        Write-Host "  [WARN]  Detected x86_64 Python on ARM64 Windows (Prism emulation)." -ForegroundColor Yellow
        Write-Host "  [WARN]  Plain client install works fine, but if you also run a local QUAD server" -ForegroundColor Yellow
        Write-Host "  [WARN]  the host-side qairt-converter will fail. Installing ARM64 Python:" -ForegroundColor Yellow
        $winget = Get-Command winget -ErrorAction SilentlyContinue
        if ($winget) {
            try {
                & winget install --id Python.Python.3.12 --source winget --architecture arm64 `
                    --silent --accept-source-agreements --accept-package-agreements
                if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq -1978335212) {
                    Write-Ok "ARM64 Python ready (re-open the shell to pick it up on PATH)."
                } else {
                    Write-Host "  [WARN]  winget exit $LASTEXITCODE; install manually if needed." -ForegroundColor Yellow
                }
            } catch {
                Write-Host ("  [WARN]  winget install failed: " + $_.Exception.Message) -ForegroundColor Yellow
            }
        } else {
            Write-Host "  [WARN]  winget not available. Install ARM64 Python from python.org/downloads/windows" -ForegroundColor Yellow
        }
    }
}

# --- Git Bash -------------------------------------------------------------
$bash = $null
foreach ($candidate in @(
    "C:\Program Files\Git\bin\bash.exe",
    "C:\Program Files (x86)\Git\bin\bash.exe",
    "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe"
)) {
    if (Test-Path $candidate) { $bash = $candidate; break }
}

if (-not $bash) {
    Write-Info "Git Bash not found. Attempting install via winget…"
    try {
        winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements
        $bash = "C:\Program Files\Git\bin\bash.exe"
    } catch {
        Write-Err "Could not install Git Bash automatically. Install from https://git-scm.com/ and re-run."
        exit 1
    }
}
Write-Ok "Git Bash: $bash"

# Set CLAUDE_CODE_GIT_BASH_PATH so Claude Code can find bash.exe.
# Persist for this session and pass it into the install.sh subprocess.
$env:CLAUDE_CODE_GIT_BASH_PATH = $bash
[System.Environment]::SetEnvironmentVariable("CLAUDE_CODE_GIT_BASH_PATH", $bash, "User")
Write-Ok "CLAUDE_CODE_GIT_BASH_PATH = $bash (set for current session + User environment)"

# --- Build install.sh args -----------------------------------------------
# install.sh resolves the coding agent via --agent > QUAD_CLIENT_DEFAULT_AGENT
# env > quad-client.toml default_agent > claude, falling back to Claude Code if
# the chosen agent isn't installed. We forward -Agent / -NoLaunch through.
# NB: avoid the automatic variable $args; use an explicit name for the splat.
$shArgs = @()
if ($Transport)       { $shArgs += "--transport=$Transport" }
if ($SshUser)         { $shArgs += "--ssh-user=$SshUser" }
if ($SshHost)         { $shArgs += "--ssh-host=$SshHost" }
if ($SshPort -ne 22)  { $shArgs += "--ssh-port=$SshPort" }
if ($SshKey)          { $shArgs += "--ssh-key=$SshKey" }
if ($SseUrl)          { $shArgs += "--sse-url=$SseUrl" }
if ($SseAuthTokenEnv) { $shArgs += "--sse-auth-token-env=$SseAuthTokenEnv" }
if ($Force)           { $shArgs += "--force" }
if ($SkipTest)        { $shArgs += "--skip-test" }
if ($FromPyPI)        { $shArgs += "--from-pypi" }
if ($Agent)           { $shArgs += "--agent=$Agent" }
if ($NoLaunch)        { $shArgs += "--no-launch" }

Write-Section "Delegating to install.sh"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$installScript = Join-Path $scriptDir "install.sh"
& $bash $installScript @shArgs
exit $LASTEXITCODE
