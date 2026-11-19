---
name: devrel-pte-run
description: Use when the user asks to "run a .pte", "run my ExecuTorch model", "profile a .pte", "deploy a .pte to my device", or invokes /devrel-pte-run. Runs/profiles an ExecuTorch .pte on the host or describes the on-device runner invocation.
trigger: "pte-run"
---

# DevRel ExecuTorch `.pte` run / profile (client)

Run or profile an existing ExecuTorch `.pte` through the DevRel MCP server, or
get the exact on-device runner invocation for a Snapdragon target.

## Profile a `.pte`

`mcp__devrel__profile_workload(model_path="<...>.pte", platform=..., runtime="npu",
profiling_level="detailed"|"linting")`. DevRel detects the `.pte` extension and
routes to ExecuTorch's native ETDump/Inspector profiler, so you get per-op
latencies and (linting) the bottleneck op — not a generic estimate.

Surface: `latency.mean_ms`, `throughput_fps`, `power_mw`, the per-op `layers`,
and for linting the `linting_layers` + `linting_optimization_hints`.

## Allocate

`mcp__devrel__orchestrate_workload(model_path="<...>.pte", power_mode=...)` to see
how the delegate partition maps onto CPU/GPU/NPU.

## Run on the host (smoke test)

A `.pte` runs host-side via the ExecuTorch pybindings — useful to validate an
XNNPACK (CPU) export. On a build-capable host the server's ExecuTorch adapter
does this; otherwise it returns a precise "missing prerequisite" message.

## Run on a Snapdragon device

For on-device execution, push three things to the target and run the runner:

1. the `.pte`
2. the `qnn_executor_runner` (built from the ExecuTorch tree, `examples/qualcomm`)
   — or a custom runner from `mcp__devrel__generate_code(sdk="executorch",
   language="cpp")`
3. the QNN backend `.so` libraries (from DevRel's QAIRT SDK)

Then:

```
./qnn_executor_runner --model_path <model>.pte
```

Use the `devrel-deploy` skill to push + run over SSH/ADB.

## Mock vs real

In mock mode, profiling returns a deterministic per-op report and a host
"run" returns a simulated result — enough to exercise the flow offline. Real
runs need the ExecuTorch runtime built on a build-capable host (and, for the
QNN delegate, the QAIRT SDK on the device). `devrel doctor` → **ExecuTorch SDK**
confirms readiness.
