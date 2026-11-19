---
name: roboagent-evaluation
description: Evaluate local Gemma 4 response quality, latency, and tool use.
---

# RoboAgent Evaluation

Use small deterministic tasks:

1. Explain `cpp/qnn_llm_host.cpp`.
2. Read `README.md` and extract the three QNN environment variables.
3. Search for `Listening on` and report the source location.
4. Inspect Git status without modifying files.
5. Run `tools\pi\test-english-output.ps1` to confirm foreign-language model
   output is suppressed by the adapter.

Record latency, whether a tool call was requested, whether it was valid, and
whether the final answer was grounded in the retrieved content. For interactive
quality checks, also record whether the response stayed entirely in English and
whether it displayed `Tokens used:` plus `QNN context:` lines.
