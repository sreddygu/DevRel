param(
    [string]$HostAddress = "127.0.0.1:18181",
    [ValidateSet("cpu", "gpu", "npu", "hybrid")]
    [string]$Compute = "npu",
    [int]$ContextWindow = 4096,
    [int]$KeepAliveSeconds = 300
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command geniex -ErrorAction SilentlyContinue)) {
    throw "geniex is not installed or is not available on PATH."
}

$model = "google/gemma-4-E4B-it-qat-q4_0-gguf:Q4_0"
$cachedModels = geniex list | Out-String
if ($cachedModels -notmatch [regex]::Escape("google/gemma-4-E4B-it-qat-q4_0-gguf")) {
    throw "Gemma is not cached. Run: geniex pull google/gemma-4-E4B-it-qat-q4_0-gguf --model-hub hf --model-type vlm"
}

Write-Host "Starting GenieX for $model"
Write-Host "Endpoint: http://$HostAddress/v1"
Write-Host "Compute: $Compute; context: $ContextWindow"

geniex serve `
    --host $HostAddress `
    --compute $Compute `
    --nctx $ContextWindow `
    --keepalive $KeepAliveSeconds
