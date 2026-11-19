---
name: quad-serve
description: Use when the user asks to "start an inference server", "expose the model as an HTTP API", "deploy to production", or invokes /quad-serve. Walks through `quad serve` setup, endpoint usage, and load testing.
trigger: "serve"
---

# QUAD Inference Server Skill

Spin up a FastAPI HTTP server that exposes a converted model on
`/infer`, `/health`, `/metrics`.

## Pre-flight

- `pip install -e .[real]` for fastapi + uvicorn (or just
  `pip install fastapi uvicorn`).
- Model must be converted to a runnable format (.bin / .dlc).

## Steps

1. **Convert** if needed (`quad-convert` skill).

2. **Start the server** in the background:
   ```bash
   quad serve path/to/model.bin --device npu --port 8080 --name mymodel
   ```

3. **Test with curl** (or the user's HTTP client):
   ```bash
   # Health check
   curl http://localhost:8080/health
   # → {"status": "healthy", "models_loaded": 1, "uptime_s": 5.2}

   # Inference (input must be base64-encoded ndarray + shape + dtype)
   curl -X POST http://localhost:8080/infer \
     -H "Content-Type: application/json" \
     -d '{
       "model_name": "mymodel",
       "inputs": {
         "input": {
           "shape": [1, 3, 224, 224],
           "dtype": "float32",
           "data_b64": "..."
         }
       }
     }'
   ```

4. **Show the user a Python client snippet** for ergonomics:
   ```python
   import base64
   import httpx
   import numpy as np

   img = np.random.randn(1, 3, 224, 224).astype(np.float32)
   payload = {
       "model_name": "mymodel",
       "inputs": {
           "input": {
               "shape": list(img.shape),
               "dtype": str(img.dtype),
               "data_b64": base64.b64encode(img.tobytes()).decode(),
           }
       }
   }
   r = httpx.post("http://localhost:8080/infer", json=payload)
   result = r.json()
   out = np.frombuffer(
       base64.b64decode(result["outputs"]["output"]["data_b64"]),
       dtype=result["outputs"]["output"]["dtype"],
   ).reshape(result["outputs"]["output"]["shape"])
   ```

5. **Monitor** with `/metrics`:
   ```bash
   watch -n 1 'curl -s http://localhost:8080/metrics | jq'
   ```

## Endpoints reference

| Method | Path                  | Purpose                                |
| :---   | :---                  | :---                                   |
| POST   | /infer                | Single inference                       |
| POST   | /infer/batch          | Batched inference                      |
| GET    | /health               | Liveness + loaded-models count         |
| GET    | /metrics              | total/avg/p99 latency + throughput     |
| GET    | /models               | List loaded models                     |
| POST   | /models/{name}/load   | Hot-load a new model                   |
| DELETE | /models/{name}        | Unload a model                         |

## Production tips

- **Sustained p99 > 2× mean** → thermal throttling. Drop to balanced
  power mode or add a cooling pad.
- **Multiple models on one NPU** → use the dynamic-batching feature
  in `ModelServer.infer_batch` to share the queue.
- **TLS / auth** → not built-in. Front the server with nginx /
  cloudflare for HTTPS + auth.
- **Restart-on-crash** → wrap `quad serve` in a systemd unit or
  Windows Service.
