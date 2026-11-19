param(
    [string]$BaseUrl = "http://127.0.0.1:18181",
    [string]$Provider = "aura-geniex",
    [string]$Model = "google/gemma-4-E4B-it-qat-q4_0-gguf:Q4_0"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command pi -ErrorAction SilentlyContinue)) {
    throw "pi is not installed. Run: npm install -g --ignore-scripts @earendil-works/pi-coding-agent"
}

$models = Invoke-RestMethod -Uri "$BaseUrl/v1/models" -TimeoutSec 10
if ($models.data.id -notcontains $Model) {
    throw "GenieX is reachable, but $Model is not advertised by $BaseUrl."
}

$smokeDirectory = Join-Path $env:TEMP "aura-pi-smoke"
New-Item -ItemType Directory -Force $smokeDirectory | Out-Null
Push-Location $smokeDirectory
try {
    $actualHostname = (hostname).Trim()
    $piOutput = pi `
        --provider $Provider `
        --model $Model `
        --api-key local `
        --offline `
        --tools bash `
        --no-session `
        --no-extensions `
        --no-skills `
        --no-context-files `
        --print `
        "Use the bash tool to run hostname. After the tool finishes, return exactly the hostname and nothing else."

    $reportedHostname = ($piOutput | Out-String).Trim()
    if ($reportedHostname -ne $actualHostname) {
        throw "Command loop failed. Expected '$actualHostname', received '$reportedHostname'."
    }

    Write-Host "PASS: pi executed hostname through Gemma and returned $reportedHostname"
}
finally {
    Pop-Location
}
