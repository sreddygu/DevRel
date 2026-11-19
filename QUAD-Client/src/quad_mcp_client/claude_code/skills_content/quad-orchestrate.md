---
name: quad-orchestrate
description: Use when the user asks to "allocate across CPU/GPU/NPU", "compare power modes", "where should this op run", or invokes /quad-orchestrate. Compares performance/balanced/efficiency modes side-by-side with tip recommendations.
trigger: "orchestrate"
---

# QUAD Orchestration Skill

Allocate inference graph nodes across CPU / GPU / NPU based on
profiling + power budget. Pick the right power mode for the user's
workload.

## Power-mode picker

Ask the user (or infer from context):

- **Real-time / camera / video** → `performance` mode (max NPU clock,
  no thermal throttling, higher power draw)
- **Interactive single-shot** → `balanced` (default, good trade-off)
- **Batch / offline / training-data labelling** → `efficiency`
  (lower clock, ~50% power, ~2-3x latency)

If the user is on battery and doing a real-time workload, surface a
warning — performance mode drains a battery in 30-60 minutes.

## Steps

1. If the user hasn't profiled yet, do that first (`quad-profile`).
   Orchestrate needs per-layer ms timings.

2. Call `mcp__quad__orchestrate_workload` for **all three** power
   modes so the user can compare:
   ```python
   for mode in ["performance", "balanced", "efficiency"]:
       result = await orchestrate_workload(model_path, mode)
   ```

3. Format with `quad.ui.format_allocation(result)`. Then add a
   side-by-side table:
   ```
   | Mode         | Latency  | Power   | NPU%  | GPU%  | CPU%  |
   | :---         | --:      | --:     | --:   | --:   | --:   |
   | performance  | 2.55ms   | 1420mW  | 70%   | 0%    | 30%   |
   | balanced     | 2.55ms   | 1420mW  | 70%   | 0%    | 30%   |
   | efficiency   | 5.00ms   | 1000mW  | 0%    | 0%    | 100%  |
   ```

4. Surface `fallback_layers` — the ops that can't run on NPU and
   will fall back to CPU regardless of mode. These are often
   custom ops or unusual shapes.

5. Recommend a mode based on the user's stated use case (use
   `quad.suggestions.suggest_power_mode`).

## Edge cases

- **`InvalidProfileError`** — if orchestrate raised this, the upstream
  profile had no per-layer data. Re-profile in `detailed` mode.
- **Empty fallback_layers + 100% NPU** — ideal! The model is fully
  HTP-compatible.
- **Many fallback_layers** — recommend writing UDOs for the hot
  ones, or accepting the latency penalty.

## When the user wants to deploy

After orchestration, call out next steps:
- `quad-codegen` to emit inference code for their target language
- `quad-serve` to spin up an HTTP server
- `quad doctor --real-mode` to verify SDK readiness before benchmarking
  on real hardware
