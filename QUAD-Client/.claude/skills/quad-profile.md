---
name: quad-profile
description: Use when the user asks to "profile a model", "find bottlenecks", "measure NPU latency", "run linting" or "QHAS profile", or invokes /quad-profile. Picks the right profiling level + renders a rich latency/utilisation summary.
trigger: "profile"
---

# QUAD Profiling Skill

Run platform profilers on a model and surface the results in a way
that makes optimisation opportunities obvious.

## Profiling levels (pick one based on the user's question)

| Question                                | Level     |
| :---                                    | :---      |
| "How fast is it on NPU?"                | detailed  |
| "What's the p99 latency?"               | detailed  |
| "Where is it slow?" / "find bottlenecks"| linting   |
| "Why aren't I getting peak NPU usage?"  | linting   |
| "I need a Chrome trace"                 | qhas      |
| "Just give me a rough number"           | basic     |

## Steps

1. Call `mcp__quad__profile_workload` with the right `profiling_level`,
   `runtime` (default `auto`), and `duration_s` (default 10, longer
   for thermally-throttling sustained tests).

2. Format with `quad.ui.format_profile(report)` — gives a latency
   table (mean / p50 / p95 / p99 / min / max), throughput row, and
   utilisation bars per compute unit.

3. **Linting mode specifically:**
   - Highlight the `linting_total_cycles` and `linting_bottleneck_count`
   - Show top 3 ops by cycle count with their `overlap_ratio` and any
     `optimization_hint`
   - Surface the `linting_optimization_hints` list — these are
     actionable rewrites the user can apply

4. **QHAS mode specifically:**
   - Mention `qhas_chrometrace_path` — the user can drag this into
     `chrome://tracing` for a kernel-level visualisation
   - Note that QHAS requires the `snpe-dlc-graph-prepare` tool +
     `qnn-profile-viewer` (run `quad doctor --real-mode` to confirm
     they're available)

5. Auto-suggest follow-ups using `quad.suggestions.suggest_optimisations`
   for any detected bottlenecks.

6. End with 1-2 tips from `quad.tips.get_tips_for("profile")`.

## Output style

For detailed profile:
```
### Profile — runtime: NPU · level: detailed

**Latency**
| Statistic | Value (ms) |
| :---      | ---:       |
| Mean      | 2.56       |
| p50       | 2.20       |
| p95       | 4.68       |
| p99       | 6.28       |

**Throughput:** 388 FPS · **Power:** 2000 mW · **Memory:** peak 50 MB

**Compute utilisation**
`███████████████████░` 95% NPU
`░░░░░░░░░░░░░░░░░░░░`  0% GPU
`█░░░░░░░░░░░░░░░░░░░`  5% CPU
```

For linting:
```
### Profile — runtime: NPU · level: linting

Total cycles: 3,753,939
Bottlenecks: 1 op with low HTP parallelism

⚠ **1 bottleneck op detected**

| # | Op       | Cycles    | Overlap | Hint                                |
| -: | :--      | --:       | --:     | :---                                |
| 4  | sub_op   | 2,165,162 | 21%     | Replace Sub with Conv on HTP v68+   |
```

## Local NPU vs CPU layer split (onnxruntime-qnn path)

When the user runs inference locally through ONNX Runtime's QNN Execution
Provider (not the remote profiler) and asks "how much ran on the NPU?" or "which
layers fell back to CPU?", use the client-side helper
`quad_mcp_client.ort_qnn.provider_split(model_path, feeds)`.

ONNX Runtime exposes **no** `get_node_provider_assignments()` API — the helper
enables session profiling and parses the emitted JSON, returning the structured
map the retrospective specified:

```python
from quad_mcp_client import ort_qnn

split = ort_qnn.provider_split("mobilenetv2_qdq.onnx")
s = split["summary"]   # {total_nodes, on_npu, on_cpu, npu_percent, cpu_percent}
```

Render it as:
```
============================================================
  QUAD PROFILE — NPU vs CPU Layer Split
============================================================
  Model     : mobilenetv2_qdq.onnx
  Provider  : QNNExecutionProvider (Hexagon HTP)

  ── Summary ──────────────────────────────
  Total ops : 52
  On NPU    : 47  (90%)
  On CPU    : 5   (10%)

  ── Recommendation ───────────────────────
  90% of ops ran on NPU — good utilisation.
  Ops that fell back to CPU are typically unsupported on HTP
  (e.g. Softmax) — consider an HTP-compatible alternative.
```

Always create the session with `ort_qnn.create_npu_session(...)` and verify
`sess.get_providers()[0] == "QNNExecutionProvider"` first — completing inference
is NOT proof the NPU was used (ORT silently falls back to CPU on QNN failure).

## When the user provides a model that hasn't been converted yet

- Run `quad-convert` first (or remind the user to).
- Profiling against an .onnx/.pt directly works in mock mode but real
  mode needs the converted .dlc / .bin.

## Known profiler failure modes (IQ-9075 findings)

1. **Remote MCP profiling has two confirmed failure modes** — surface them
   before blaming the model:
   - A **`PermissionError`** on the remote host's SDK execute bit.
   - A **server-side filesystem-visibility wall**: a local model path is not
     visible to a profiling MCP server running on a *different* host.
   When either hits, fall back to the proven local/on-device paths:
   `profile_local.py`, `board_profile.py profile`, or the direct-execution
   pattern in `/quad-qnn-runtime-debug`.

2. **Version-controlled reproducibility — always record the exact
   `onnxruntime` version.** It changes both latency and loadability:
   - A real **2.4× latency swing** (14.85 ms vs 6.14 ms) between ORT versions
     on identical hardware.
   - A **version-dependent load failure** (a duplicate-node-name rejection in
     1.27.0 that 1.22.1 tolerates).
   Never treat cross-version numbers as comparable; pin and report the version
   alongside every result.

<!-- skills-hub:begin -->

## Compatibility

| Item | Details |
| --- | --- |
| Devkits | Not device-specific |
| Target OS | No target OS constraint declared |
| Host OS | Windows, Linux (or WSL) |
| Requirements | Python 3.10+; a reachable QUAD MCP server; Qualcomm AI Runtime (QAIRT) SDK 2.47 and Snapdragon X Elite for NPU workflows |

References: [QUAD Client README](https://github.com/sreddygu/DevRel/blob/main/QUAD-Client/README.md).

## Example prompts

- Profile my model and find bottlenecks
- Measure NPU latency for this model
- Run QHAS profiling
- Lint my model for NPU-unfriendly ops
- Which layers of my model are not running on the NPU?
- Compare the latency of my int8 and fp16 models

<!-- skills-hub:end -->
