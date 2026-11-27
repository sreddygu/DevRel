# Project verification run

One pass over every project on 2026-11-27. Host: Windows-on-Snapdragon PC (Python 3.12
ARM64). Board: Dragonwing IQ-8275 (IQ8), Qualcomm Linux 2.0, aarch64, Python 3.14.4
(trimmed standard library: no `html`, `statistics`), 11 GiB RAM, adsp / gpdsp0 / cdsp
running. No packages were installed on the board; run output was written to `/tmp` and
removed afterwards, and nothing from these runs is committed.

| Project | What was run | Where | Result |
| --- | --- | --- | --- |
| AURA | `pytest` (116 tests); `examples/memory_demo.py` | PC; IQ8 | Pass; demo stored 5 events, answered `where_is` and `recall` |
| AI-Across-Devices | Hub serve + token-protected pull + idempotent re-pull | IQ8 | Pass (2 added, then 0; raw attribute stripped) |
| Wearable-AI | Simulated sensor loop, 81 s of data | IQ8 | Pass (6 context events, 1 burst) |
| EdgeAgent | `pytest` (about 320 tests); `doctor`; `agent.py` tool-using prompt | PC; IQ8 | Pass; doctor 0 errors / 8 warnings (no QAIRT SDK on PATH); agent on IQ8 used a tool through a tunnel to a PC model |
| GesturDJ | Synthetic dataset, quality check, sklearn training, smoke test; `discover_host.py` | PC; IQ8 | Pass (baseline 0.70 on 30 synthetic held-out samples); IQ8 lacks sklearn / onnxruntime |
| GesturDJ (music model) | Read-only NPU preflight | IQ8 | QNN HTP v75 runtime and compiled contexts present, 0 external aborts, no stale server. Graph load not run (a hung call wedges the NPU) |
| VSaaS | Cloud API + simulated edge agent | PC; IQ8 edge to PC cloud | Pass (events stored and listed); real YOLOv8 / QNN path not run |
| qli_dogfooding | `qli_device_validation.py` (13 checks) | IQ8 over SSH | Pass, file-transfer hash matched, deploy loop worked |
| RoboAgent | Python and PowerShell syntax; mock-host protocol test | PC | Pass (`PROTOCOL_TEST_PASSED`); QNN runners and Gemma model are not in the checkout, so no on-NPU run |
| wake_word | Syntax of scripts and notebook | PC | Compiles; not trained or run (needs the Speech Commands dataset and PyTorch) |
| LLM | Syntax of scripts, notebook, shell | PC | Compiles; not run (needs llama.cpp binaries and a GGUF model) |
| mojo-max-int | Notebook and shell syntax | PC | Parses; not run (Mojo toolchain not installed) |
| Developer-Journey, Edge-AI-for-Everyone, Multiverse-of-Developers, XR-Experiences | Link check | n/a | Narrative briefs with no code; all links resolve |

Repo-wide: 498 relative Markdown links checked, 0 broken after fixes; the skills catalog
check reports 16 skills, 0 problems.

Findings worth knowing:

- The IQ8's Python lacks `html` and `statistics`; the handoff server and wearable classifier
  avoid both. AURA's base install needs `pydantic`, which the board does not have, so on the
  board only AURA's stdlib + numpy parts (events, memory) run.
- `agent.py --base-url` takes the bare host and port (it adds `/v1` itself), unlike the
  `handoff ask` command, which takes the `/v1` URL.
- The PC has QAIRT 2.51; several docs and metadata pages say 2.47.
