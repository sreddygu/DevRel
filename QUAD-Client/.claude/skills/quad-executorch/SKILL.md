---
name: quad-executorch
description: Use when the user asks to "export a PyTorch model to ExecuTorch", "make a .pte", "run my PyTorch model on the NPU via ExecuTorch", "use the ExecuTorch QNN backend", or invokes /quad-executorch. Drives the PyTorch→.pte→profile→runner flow against a QUAD MCP server and points at the executorch_mobilenet sample.
trigger: "executorch"
---

# QUAD ExecuTorch (client)

Take a **PyTorch** model to an on-device **ExecuTorch `.pte`** through the QUAD
MCP server: export + lower to a Qualcomm delegate, profile per-op, allocate
across compute units, and generate runner code.

## When to use ExecuTorch vs QNN/SNPE

- **ExecuTorch** (`target_sdk="executorch"`) — PyTorch source, want the
  PyTorch-native `.pte`, the delegate **partition map** (NPU vs CPU ops), or a
  CPU fallback (XNNPACK).
- **QNN/SNPE** — ONNX/TF source, or you want a `.bin`/`.dlc` for QUAD's
  existing runtime.

## Steps (MCP tool calls)

1. `mcp__quad__hardware_detect(platform)` — chipset + NPU.
2. `mcp__quad__convert_model`:
   - `source_format="pytorch"`, `target_sdk="executorch"`
   - `runtime`: `qnn-htp` (NPU, default) / `qnn-gpu` (Adreno) / `xnnpack` (CPU)
     / `vulkan` / `arm` / …
   - `quantization`: `int8` (NPU) / `fp16` / `fp32`
   - Surface `output_path` (the `.pte`) and the partition map:
     `delegated_op_count` / `fallback_op_count` / `fallback_ops` — **the
     headline metric**. Low delegation = ops fall back to CPU = latency hops.
3. `mcp__quad__profile_workload(model_path="<...>.pte", profiling_level="detailed"|"linting")`
   — QUAD routes `.pte` to ExecuTorch's ETDump/Inspector path (per-op).
4. `mcp__quad__orchestrate_workload(model_path="<...>.pte", power_mode=...)`
   — the CPU/GPU/NPU split.
5. `mcp__quad__generate_code(sdk="executorch", language="python"|"cpp",
   model_path="<...>.pte")` — emits an export/run script or a C++ runner +
   CMakeLists.

## The runnable sample

Point the user at `samples/executorch_mobilenet/` — a one-command end-to-end
demo of exactly this flow:

```
cd samples/executorch_mobilenet
./run.ps1                                   # one-time deps (just fastmcp for mock)
.venv/Scripts/python.exe run_executorch.py  # mock end-to-end, any host
```

It runs in **mock mode** by default (no torch / NPU / QNN SDK), writes a stub
`.pte`, and emits the generated runner under `generated/`. Add `--real` on a
build-capable Snapdragon host for a genuine export.

## Mock vs real

- **Mock** — any host; deterministic stub `.pte` + simulated partition/profile.
- **Real** — needs Python 3.10–3.13 (ExecuTorch is `<3.14`), `torch` +
  `executorch`, and QUAD's QAIRT SDK for the QNN delegate. Run `quad doctor`
  (or `mcp__quad__` doctor flow) and confirm **ExecuTorch SDK** is green first.
  If the host isn't ready, the server returns a precise missing-prerequisite
  message — relay it.

## Follow-ups

- To run / deploy the `.pte` on a device, use the `quad-pte-run` skill.
- Start with `--runtime xnnpack` if there's no NPU — it validates the export
  end to end on CPU.
