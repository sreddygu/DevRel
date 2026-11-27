# pi + Gemma 4 + ExecuTorch (warm named-pipe host)

> This is the **warm** variant of `docs/PI_EXECUTORCH.md`. Both drive Gemma 4 on
> the Snapdragon NPU through ExecuTorch; the difference is model-load cost.
> `PI_EXECUTORCH.md` reloads `llama_main` on every request. This path keeps
> `qnn_llm_host.exe` **warm** — model + QNN context restored once (~2s), then
> reused — so an agent loop with many tool round-trips isn't paying the load cost
> every turn.

```text
pi agent harness
    -> OpenAI Chat Completions
    -> aura-executorch-server --backend pipe-host
    -> bin/qnn_llm_host.exe  (persistent, \\.\pipe\gemma4)
    -> Gemma 4 E2B .pte  (loaded once, kept warm)
```

The adapter reuses AURA's existing prompt rendering and tool-call parsing
unchanged — only the token source differs. `PipeHostManager`
(`aura.agent.pipe_host`) owns the host process: it spawns it warm, sends each
request over the named pipe, and — because the host keeps **one continuous
KV-cache that cannot be reset in-band** — respawns the host before the running
position would exceed a conservative ceiling. See the `aura.agent.pipe_host`
module docstring for why.

## Prerequisites

Everything but the QAIRT SDK ships inside AURA:

- `bin/qnn_llm_host.exe` + `bin/RelWithDebInfo/qnn_executorch_backend.dll` —
  vendored (local `bin/` folder, not committed).
- `models/gemma4_e2b_sc8380xp_ctxt_4000_ar_l-128/` — the Gemma-4 E2B `.pte` +
  tokenizer (~2.8 GB; local `models/` folder, not committed).
- A **QAIRT SDK** installed on the machine (not vendored — it's large and
  machine-specific). Example: `C:\Qualcomm\AIStack\QAIRT\2.51.40.260930`. Use a
  version **>=** the one the `.pte` was compiled against (an older runtime fails
  with `err 5000`).
- Snapdragon X Elite (SC8380XP) → HTP arch **v73**.

## 1. Install AURA

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

## 2. Start the warm pipe-host adapter

The three QNN environment variables that `qnn_llm_host.exe` needs (`QNN_SDK_ROOT`,
the backend dir + `lib\aarch64-windows-msvc` on `Path`, `ADSP_LIBRARY_PATH`) are
assembled **for you** by `PipeHostManager` from `--qnn-sdk-root`, `--backend-dir`,
and `--hexagon-arch`. All paths default to the vendored AURA locations, so from
the AURA repo root the only machine-specific value is the SDK root:

```powershell
aura-executorch-server `
  --backend pipe-host `
  --qnn-sdk-root "C:\Qualcomm\AIStack\QAIRT\2.51.40.260930"
```

That resolves the defaults: `--host-bin ./bin/qnn_llm_host.exe`,
`--backend-dir ./bin/RelWithDebInfo`, `--model-path` / `--tokenizer-path` from
`AURA_MODEL_PATH` / `AURA_TOKENIZER_PATH` (or pass them explicitly), `--pipe-name
gemma4`, `--decoder-model-version gemma4`, `--seq-len-ceiling 3800`,
`--hexagon-arch 73`, `--port 8082`. Fully spelled out:

```powershell
aura-executorch-server `
  --backend pipe-host `
  --host-bin ".\bin\qnn_llm_host.exe" `
  --model-path ".\models\gemma4_e2b_sc8380xp_ctxt_4000_ar_l-128\gemma4_e2b_sc8380xp_ctxt_4000-001.pte" `
  --tokenizer-path ".\models\gemma4_e2b_sc8380xp_ctxt_4000_ar_l-128\tokenizer.json" `
  --decoder-model-version gemma4 `
  --pipe-name gemma4 `
  --seq-len-ceiling 3800 `
  --qnn-sdk-root "C:\Qualcomm\AIStack\QAIRT\2.51.40.260930" `
  --backend-dir ".\bin\RelWithDebInfo" `
  --hexagon-arch 73 `
  --model gemma-4-e2b-executorch `
  --host 127.0.0.1 --port 8082
```

Or set the `AURA_*` keys from `.env.example` (the `pipe-host` block) and run with
just `--backend pipe-host`. First start pays the ~2s warm-load once; watch for the
host's `Listening on \\.\pipe\gemma4` line, after which the adapter connects.

Confirm the endpoint is alive:

```powershell
curl http://127.0.0.1:8082/v1/models
```

## 3. Configure pi

Identical to `docs/PI_EXECUTORCH.md` — the endpoint shape is unchanged. Add the
provider to `~/.pi/agent/models.json` (use a distinct provider id if you keep both
paths side by side):

```json
{
  "providers": {
    "aura-pipe-host": {
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
          "name": "Gemma 4 E2B (ExecuTorch, warm host)",
          "reasoning": false,
          "input": ["text"],
          "contextWindow": 4000,
          "maxTokens": 512,
          "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}
        }
      ]
    }
  }
}
```

## 4. Validate basic command execution

```powershell
mkdir C:\Temp\aura-pi-smoke; cd C:\Temp\aura-pi-smoke
pi --provider aura-pipe-host `
  --model gemma-4-e2b-executorch `
  --api-key local `
  "Use the bash tool to run hostname, then return only the command output."
```

The complete loop is the same five steps as the reload-per-call path; the win is
that the **second and later** turns don't reload the model. For a server-only
check, post a tool schema directly (see the `curl` example in
`docs/PI_EXECUTORCH.md` §4).

**Read the actual generated text** before trusting a run — healthy tok/s is not
proof of correct output — a documented QNN-on-Windows gotcha.

## Notes and limits

- **KV-cache / respawn.** The host advances one continuous conversation position
  and aborts hard on context overflow. `PipeHostManager` estimates the position
  (chars/token heuristic) and kills+relaunches the host before `--seq-len-ceiling`
  to reset it. If you see the host process cycle mid-session, that's the guard
  firing — lower the ceiling if aborts still slip through, raise it (up to
  `context_len − AR` = 3872 for this model) for fewer respawns.
- **Context window.** Compiled at 4000 tokens. Derrick speculates ~8K–9K may be
  reachable on a re-export before significant degradation, but that is **untested**
  — the shipped `.pte` is 4000.
- **Windows-only.** Named pipes (`\\.\pipe\...`) are a Windows transport; this
  backend targets the Snapdragon X Elite dev box, not the on-device Linux boards
  (those use the GenieX / Genie HTTP paths).

## Current boundary

Same as the ExecuTorch path: this validates one local model, one agent harness,
and basic tool calling. AURA's robot tools, ROS2 delegation, and Milestone 5
safety policy for physical actuation are the next slice, after the warm command
loop is proven on target hardware.
