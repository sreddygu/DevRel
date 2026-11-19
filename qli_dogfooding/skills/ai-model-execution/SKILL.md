# AI Model Execution

Run a model only after discovering the actual runner, model path, backend, and
input format on the target.

1. Require a valid image and runner command. Do not copy command arguments from
   another device without verifying them.
2. Run `python src/qli_ai_apps.py classify --image <image> --command <runner...>`.
3. Capture the runner return code, model/backend identity, parsed result, and
   timing.
4. Mark the result blocked when the runner, model, backend, or required input is
   unavailable; do not report completion from file presence.

This skill executes inference. Use the benchmark skill for repeatable latency or
throughput measurement.
