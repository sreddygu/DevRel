# pi + Gemma 4 + ExecuTorch

> This adapter remains available for a future ExecuTorch `.pte` delivery. The
> currently validated Snapdragon X Elite path uses the Qualcomm AI Hub GenieX
> package; see `docs/PI_GENIEX.md`.

This is the first-phase integration path for using the pi coding-agent harness
with a local Gemma 4 E2B model executed by ExecuTorch:

```text
pi agent harness
    -> OpenAI Chat Completions
    -> aura-executorch-server
    -> ExecuTorch llama_main
    -> Gemma 4 E2B .pte
```

The adapter keeps the seam intentionally small. pi owns the agent loop and tool
execution. AURA translates messages and tool schemas into a compact prompt,
runs the local model, and translates its decision back into an OpenAI-style
assistant answer or function tool call.

## 1. Install AURA

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

On Windows, activate with `.venv\Scripts\activate`.

## 2. Start the ExecuTorch adapter

Use the `llama_main` binary and Gemma artifacts produced by the ExecuTorch
export/build flow:

```bash
aura-executorch-server \
  --runner-bin /path/to/llama_main \
  --model-path /path/to/gemma-4-e2b.pte \
  --tokenizer-path /path/to/tokenizer.model \
  --model gemma-4-e2b-executorch \
  --host 127.0.0.1 \
  --port 8082 \
  --max-new-tokens 512 \
  --temperature 0
```

The adapter uses the current ExecuTorch example-runner flags
`--model_path`, `--tokenizer_path`, `--prompt_file`, `--max_new_tokens`, and
`--temperature`. Use repeatable `--runner-arg` options for flags that must appear
immediately after the runner binary.

Confirm that the endpoint is alive:

```bash
curl http://127.0.0.1:8082/v1/models
```

## 3. Configure pi

Install pi if needed:

```bash
npm install -g --ignore-scripts @earendil-works/pi-coding-agent
```

Add this provider to `~/.pi/agent/models.json`:

```json
{
  "providers": {
    "aura-executorch": {
      "baseUrl": "http://127.0.0.1:8082/v1",
      "api": "openai-completions",
      "apiKey": "local",
      "compat": {
        "supportsDeveloperRole": false,
        "supportsReasoningEffort": false,
        "supportsStrictMode": false
      },
      "models": [
        {
          "id": "gemma-4-e2b-executorch",
          "name": "Gemma 4 E2B (ExecuTorch)",
          "reasoning": false,
          "input": ["text"],
          "contextWindow": 4000,
          "maxTokens": 512,
          "cost": {
            "input": 0,
            "output": 0,
            "cacheRead": 0,
            "cacheWrite": 0
          }
        }
      ]
    }
  }
}
```

The dummy API key is required by pi for keyless local providers; the AURA
adapter does not authenticate local requests. Keep the server bound to
`127.0.0.1` unless it is protected by a trusted network boundary.

## 4. Validate basic command execution

Run pi in a disposable directory and explicitly request a harmless command:

```bash
mkdir -p /tmp/aura-pi-smoke && cd /tmp/aura-pi-smoke
pi --provider aura-executorch \
  --model gemma-4-e2b-executorch \
  --api-key local \
  "Use the bash tool to run pwd, then return only the command output."
```

Success requires the complete loop:

1. pi sends messages and its bash tool schema to the AURA endpoint.
2. Gemma returns an `AURA_RESPONSE` tool decision.
3. AURA emits an OpenAI `tool_calls` response.
4. pi executes `pwd` and sends the tool result back.
5. Gemma returns the final answer containing the disposable directory path.

For a server-only check, post a tool schema directly:

```bash
curl http://127.0.0.1:8082/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma-4-e2b-executorch",
    "messages": [{"role": "user", "content": "Run pwd"}],
    "tools": [{
      "type": "function",
      "function": {
        "name": "bash",
        "description": "Run a shell command",
        "parameters": {
          "type": "object",
          "properties": {"command": {"type": "string"}},
          "required": ["command"]
        }
      }
    }]
  }'
```

The expected response has `finish_reason: "tool_calls"` and a `bash` function
call whose JSON arguments request `pwd`. This direct check does not execute the
command; pi performs execution in the full smoke test.

## Current boundary

This phase validates one local model, one agent harness, and basic tool calling.
It does not yet add AURA robot tools, ROS2 delegation, long-running model
sessions, or safety policy for physical actuation. Those belong in the next
Milestone 5 slice after the command loop is proven on target hardware.
