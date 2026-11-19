---
name: quad-recommend
description: Use when the user asks "what's the best way to deploy this model on Snapdragon", "recommend an approach", "should I use INT4 or INT8", "NPU or GPU", or invokes /quad-recommend. Synthesises model + target + use case into specific recommendations.
trigger: "recommend"
---

# QUAD Recommendations Skill

Given a model + target hardware + use case, produce a concrete
deployment recommendation with rationale and commands to copy.

## Information you need from the user

If any of these are unclear, ask before recommending:

1. **Model** — name + format (ONNX/PyTorch/TF) + size
2. **Target hardware** — Snapdragon X Elite / 8 Elite / QCS2210 / etc.
3. **Use case** — `realtime` (camera/video), `interactive` (single
   inference), `batch` (offline)
4. **Power constraint** — on AC, on battery, sustained vs spike
5. **Accuracy floor** — can they tolerate 1-3% drop for INT4? Or do
   they need INT8 minimum?

## How to build the recommendation

Use the `quad.suggestions` engine:

```python
from quad.suggestions import suggest_for_workflow

# Run the full pipeline first to get profile + coverage data
hardware = mcp__quad__hardware_detect("windows")
conversion = mcp__quad__convert_model(...)
profile = mcp__quad__profile_workload(..., profiling_level="linting")

recs = suggest_for_workflow(
    profile=profile,
    coverage=qbin.metadata.get("coverage"),
    conversion=conversion,
    use_case="realtime",
    on_battery=False,
)

for rec in recs:
    print(rec.to_markdown())
```

Each `Suggestion` has:
- `title` — short headline
- `rationale` — 1-2 sentences why
- `severity` — info / recommend / warning / critical
- `command` — copy-paste-able next step (when applicable)
- `category` — quantization / runtime / power / optimisation

## Output style

Group by category. Within each category, sort by severity (critical
first). Example:

```markdown
## QUAD recommendation for MobileNetV2-1.0 on Snapdragon X Elite

### Quantization
💡 **Quantize to INT8 to shrink ≥4× and unlock NPU**
  Model is 13 MB at FP32. INT8 typically achieves 4× compression with <1% accuracy
  drop. Required for HTP NPU execution.
  ```
  quantization="int8"
  ```

### Runtime
💡 **Run on NPU — 100% op coverage, ideal for this model**
  All 14 ops are HTP-compatible. Expect 4-10× throughput vs CPU at <50% the power.
  ```
  runtime="npu"
  ```

### Power
💡 **Use `performance` power mode for real-time workloads**
  Camera/video pipelines need consistent sub-frame latency. Performance mode pins
  the NPU at max clock and disables thermal throttling.
  ```
  power_mode="performance"
  ```

### Final command

```python
result = await convert_model(
    model_path="mobilenetv2.onnx",
    source_format="onnx",
    target_sdk="qnn",
    quantization="int8",
    input_layout="nchw",
    channel_order="rgb",
)
```
```

## Edge cases

- **Custom op in the model** — if `coverage_pct < 80`, recommend
  GPU rather than NPU (avoids transfer cost) OR writing a UDO.
- **Batch + on battery** — efficiency mode is almost always right.
- **LLM / transformer** — recommend FP16 + INT4 weights via AIMET +
  KV-cache. Profile latency per-token, not per-inference.
