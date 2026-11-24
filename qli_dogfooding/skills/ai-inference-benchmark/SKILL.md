---
name: ai-inference-benchmark
description: "Benchmark a model command found on a Qualcomm Linux (QLI) device with explicit warm-up and iteration counts."
version: 2.0.0
---

# AI Inference Benchmark

Measure a model only after it has executed successfully on the target.

1. Require the validated runner command, iteration count, and warmup count.
2. Run `python src/qli_ai_apps.py benchmark --iterations <count> --warmup
   <count> --command <runner...>`.
3. Capture command, model/backend identity, warmup, iterations, return code, and
   reported timing.
4. Keep benchmark evidence separate from model artifacts and do not compare runs
   with different commands, backends, or settings as though they were equivalent.

This skill reports a measurement; it does not select a model or change runtime
configuration.
