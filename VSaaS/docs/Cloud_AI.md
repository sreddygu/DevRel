# Cloud AI Work Flow

This document outlines how to launch, drive, and validate the VSaaS Cloud API
and its natural‑language query capability.


## LLM Configuration

VSaaS Cloud API supports event summarization via an OpenAI-compatible LLM server.
Configure in your shell (do **not** store secrets in this repo):

```bash
# Hosted OpenAI-compatible endpoint:
export VSAAS_LLM_BASE_URL="https://api.example.com/v1"
export VSAAS_LLM_MODEL="qwen3_vl_32b_instruct"
export VSAAS_LLM_API_KEY="Stored in password manager"
# Optional for gateways that require a separate x-apikey header:
# export VSAAS_LLM_X_APIKEY="Stored in password manager"
export VSAAS_LLM_DEBUG=1

# Fallback endpoint (local Qwen server):
export VSAAS_LLM_BASE_URL="http://127.0.0.1:8080"
export VSAAS_LLM_MODEL="qwen3_vl_32b_instruct"
```

## 1. Start the Cloud API
```bash
./scripts/run_cloud.sh
```

## 2. Post events into the Cloud API

### Option A: run an edge simulation
```bash
./scripts/run_edge_sim.sh
```

### Option B: replay stored events
```bash
python3 ./scripts/replay_events.py \
  --db-path data/events.db \
  --base-url http://127.0.0.1:9000 \
  --batch-size 25
```

## 3. Validate service health and raw events
```bash
curl -s http://127.0.0.1:9000/health
curl -s http://127.0.0.1:9000/events?limit=5 | jq .
```

## 4. Run natural‑language query (LLM summaries)

Export LLM configuration in your shell (do **not** store secrets in this repo):

```bash
# Hosted OpenAI-compatible LLM endpoint:
export VSAAS_LLM_BASE_URL="https://api.example.com/v1"
export VSAAS_LLM_MODEL="qwen3_vl_32b_instruct"
export VSAAS_LLM_API_KEY="Stored in password manager"
# Optional for gateways that require a separate x-apikey header:
# export VSAAS_LLM_X_APIKEY="Stored in password manager"
export VSAAS_LLM_DEBUG=1

# Fallback LLM endpoint: local Qwen server on IQ8
export VSAAS_LLM_BASE_URL="http://127.0.0.1:8080"
export VSAAS_LLM_MODEL="qwen3_vl_32b_instruct"

./scripts/run_query.sh "summarize recent events"
```

## Notes

## Example

```bash
# Health check
curl -s http://127.0.0.1:9000/health | jq .

# List recent events (metadata only)
curl -s http://127.0.0.1:9000/events?limit=2 | jq .

# Summarize via the configured hosted or local LLM
./scripts/run_query.sh "summarize recent events" | jq .
```
