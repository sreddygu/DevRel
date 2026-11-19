# pi + Gemma 4 E4B + GenieX

This is AURA's validated Snapdragon X Elite development path for the first pi
agent-harness milestone:

```text
pi coding agent
    -> OpenAI Chat Completions
    -> GenieX server
    -> Gemma 4 E4B Q4_0
    -> Snapdragon X Elite NPU
```

Validated on September 17, 2026 with GenieX CLI `0.6.1`, a 4096-token context,
and the Qualcomm AI Hub model
`google/gemma-4-E4B-it-qat-q4_0-gguf:Q4_0`.

## Prerequisites

- Windows on Snapdragon X Elite.
- GenieX CLI on `PATH`.
- Node.js and npm.
- pi coding agent:

```powershell
npm install -g --ignore-scripts @earendil-works/pi-coding-agent
```

## 1. Pull Gemma

```powershell
geniex pull google/gemma-4-E4B-it-qat-q4_0-gguf `
  --model-hub hf `
  --model-type vlm
```

The cached package is approximately 5.7 GiB and includes the Q4_0 language
model plus its multimodal projector.

## 2. Configure pi

Copy `deploy/pi/models.aura-geniex.json` to `~/.pi/agent/models.json`. If that
file already contains custom providers, merge the `aura-geniex` provider rather
than replacing the file.

Confirm discovery:

```powershell
pi --list-models aura-geniex
```

## 3. Start GenieX

Run the checked-in launcher and keep the terminal open:

```powershell
.\scripts\start_geniex_gemma.ps1
```

The server listens on `http://127.0.0.1:18181` and advertises the model through
`/v1/models`.

## 4. Configure AURA

Set these values in `.env` or the current shell:

```text
AURA_LLM_BASE_URL=http://127.0.0.1:18181
AURA_LLM_MODEL=google/gemma-4-E4B-it-qat-q4_0-gguf:Q4_0
AURA_LLM_NO_THINK=false
```

This uses the existing `LocalLLM` seam; no GenieX-specific Python adapter is
required.

Run AURA's grounded memory demo:

```powershell
.\.venv\Scripts\python.exe examples\ask_demo.py
```

## 5. Validate pi command execution

With the GenieX server running:

```powershell
.\scripts\test_pi_geniex.ps1
```

The smoke test enables only pi's `bash` tool, asks Gemma to run `hostname`, and
compares the returned value with the machine's real hostname. A successful run
prints:

```text
PASS: pi executed hostname through Gemma and returned <hostname>
```

## Safety boundary

This proves local command selection and execution, not safe physical actuation.
Keep GenieX bound to `127.0.0.1`. Before connecting ROS2 or robot controls, add
an allowlisted AURA tool adapter with argument validation, timeouts, emergency
stop behavior, and an action Event audit trail.

AURA now provides that software seam in `aura.agent.robot`. It remains disabled
from pi until the target robot topic and physical emergency-stop behavior are
validated on hardware.

## ExecuTorch alternative

`docs/PI_EXECUTORCH.md` documents AURA's separate OpenAI-compatible adapter for
a future Gemma `.pte` runner. Use this GenieX path for the currently validated
Qualcomm AI Hub package.
