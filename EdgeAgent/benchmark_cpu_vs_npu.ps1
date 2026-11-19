param(
  [string]$CpuBaseUrl = "http://127.0.0.1:8080",
  [string]$NpuBaseUrl = "http://127.0.0.1:8081",
  [string]$CpuModel = "gemma-4-E4B-it-Q4_K_M.gguf",
  [string]$NpuModel = "qwen3-4b-genie",
  [string]$Prompt = "Give a 1-sentence summary of what an NPU is.",
  [int]$Iterations = 3,
  [int]$TimeoutSec = 300
)

$ErrorActionPreference = "Stop"

function Invoke-ChatCompletionJson {
  param(
    [string]$BaseUrl,
    [string]$Model,
    [string]$UserPrompt,
    [int]$TimeoutSec
  )

  $body = @{
    model    = $Model
    messages = @(@{ role = "user"; content = $UserPrompt })
  } | ConvertTo-Json -Depth 6

  $resp = Invoke-RestMethod -Uri ($BaseUrl.TrimEnd("/") + "/v1/chat/completions") `
    -Method Post -ContentType "application/json" -Body $body -TimeoutSec $TimeoutSec

  return $resp
}

function Get-EstimatedTokenCount {
  param([string]$Text)
  if (-not $Text) { return 0 }

  # Fallback only -- server-reported usage is preferred by the caller. Use a
  # uniform chars/4 estimate (matching agent.py's _estimate_tokens) so the CPU
  # and NPU numbers are measured the SAME way and stay comparable, regardless of
  # whether a response looks like JSON or prose.
  $t = $Text.Trim()
  return [int][math]::Max(1, [math]::Ceiling($t.Length / 4.0))
}

function Measure-Endpoint {
  param(
    [string]$Name,
    [string]$BaseUrl,
    [string]$Model
  )

  Write-Host ""
  Write-Host "== $Name ==" -ForegroundColor Cyan
  Write-Host "base-url: $BaseUrl"
  Write-Host "model:    $Model"

  $timesMs = @()
  $completionTokens = @()
  $lastText = $null

  for ($i = 1; $i -le $Iterations; $i++) {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $resp = Invoke-ChatCompletionJson -BaseUrl $BaseUrl -Model $Model -UserPrompt $Prompt -TimeoutSec $TimeoutSec
    $sw.Stop()
    $timesMs += [int]$sw.Elapsed.TotalMilliseconds

    $lastText = $resp.choices[0].message.content
    $ct = $null
    try { $ct = $resp.usage.completion_tokens } catch { $ct = $null }
    if ($ct -eq $null) { $ct = Get-EstimatedTokenCount -Text $lastText }
    $completionTokens += [int]$ct

    Write-Host ("iter {0}/{1}: {2} ms" -f $i, $Iterations, $timesMs[-1])
  }

  $avg = [math]::Round(($timesMs | Measure-Object -Average).Average, 1)
  $min = ($timesMs | Measure-Object -Minimum).Minimum
  $max = ($timesMs | Measure-Object -Maximum).Maximum
  $avgSec = [math]::Max(0.001, ($avg / 1000.0))
  $avgCompletionTokens = [math]::Round(($completionTokens | Measure-Object -Average).Average, 1)
  $tokPerSec = [math]::Round(($avgCompletionTokens / $avgSec), 2)

  Write-Host ("avg/min/max: {0} / {1} / {2} ms" -f $avg, $min, $max) -ForegroundColor Yellow
  Write-Host ("avg completion tokens: {0}  (server usage if available; else estimated)" -f $avgCompletionTokens) -ForegroundColor Yellow
  Write-Host ("approx tokens/sec: {0}" -f $tokPerSec) -ForegroundColor Yellow
  Write-Host "sample output:"
  Write-Host $lastText

  [pscustomobject]@{
    Name     = $Name
    BaseUrl  = $BaseUrl
    Model    = $Model
    TimesMs  = $timesMs
    CompletionTokens = $completionTokens
    AvgMs    = $avg
    MinMs    = $min
    MaxMs    = $max
    AvgCompletionTokens = $avgCompletionTokens
    TokensPerSec = $tokPerSec
    Sample   = $lastText
  }
}

# quick reachability checks
try { Invoke-RestMethod -Uri ($CpuBaseUrl.TrimEnd("/") + "/v1/models") -TimeoutSec 2 | Out-Null } catch { Write-Warning "CPU server not reachable at $CpuBaseUrl (start llama-server first)." }
try { Invoke-RestMethod -Uri ($NpuBaseUrl.TrimEnd("/") + "/v1/models") -TimeoutSec 2 | Out-Null } catch { Write-Warning "NPU server not reachable at $NpuBaseUrl (start genie_server first)." }

$cpu = Measure-Endpoint -Name "CPU (llama.cpp)" -BaseUrl $CpuBaseUrl -Model $CpuModel
$npu = Measure-Endpoint -Name "NPU (Genie)" -BaseUrl $NpuBaseUrl -Model $NpuModel

Write-Host ""
Write-Host "== Summary ==" -ForegroundColor Green
Write-Host ("CPU avg: {0} ms   (min/max {1}/{2})" -f $cpu.AvgMs, $cpu.MinMs, $cpu.MaxMs)
Write-Host ("NPU avg: {0} ms   (min/max {1}/{2})" -f $npu.AvgMs, $npu.MinMs, $npu.MaxMs)
Write-Host ("CPU tok/s: {0}   (avg completion tokens {1})" -f $cpu.TokensPerSec, $cpu.AvgCompletionTokens)
Write-Host ("NPU tok/s: {0}   (avg completion tokens {1})" -f $npu.TokensPerSec, $npu.AvgCompletionTokens)

if ($cpu.AvgMs -gt 0) {
  $latencySavingsPct = [math]::Round((($cpu.AvgMs - $npu.AvgMs) / $cpu.AvgMs) * 100.0, 1)
  $speedupX = [math]::Round(($cpu.AvgMs / [math]::Max(1.0, $npu.AvgMs)), 2)

  if ($latencySavingsPct -ge 0) {
    Write-Host ("NPU is ~{0}% lower latency than CPU for this prompt (≈{1}× faster on avg)." -f $latencySavingsPct, $speedupX) -ForegroundColor Yellow
  } else {
    Write-Host ("NPU is ~{0}% higher latency than CPU for this prompt (CPU ≈{1}× faster on avg)." -f (-1 * $latencySavingsPct), $speedupX) -ForegroundColor Yellow
  }
}

Write-Host ""
Write-Host "Notes:" -ForegroundColor DarkGray
Write-Host "- This measures end-to-end request latency (HTTP + token generation)."
Write-Host "- tokens/sec uses server-reported usage when available; otherwise it is an estimate from the returned text."
Write-Host "- CPU vs NPU are usually different model formats and may differ in quality/length."
