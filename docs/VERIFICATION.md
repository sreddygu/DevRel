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
- The PC has QAIRT 2.51; docs and metadata that said 2.47 were updated (see the follow-up run below).

## Follow-up run: the items that did not run, on QAIRT 2.51 (2026-11-27)

The PC has QAIRT 2.51.40.260930 and the home IQ8's runtime (`~/diffrhythm/qnn_rt`, `~/ace_step_iq8/qnn_rt`) is QNN 2.51.40.260930
too, so docs that said 2.47 were updated to 2.51 (host SDK requirements, SDK paths, stories). Dated evidence logs, board-version
notes for other images, test fixtures and per-skill evidence were left at the version they were observed with.

| Project | What was run | Result |
| --- | --- | --- |
| GesturDJ (music model) | One ACE-Step transformer block (`ctx/block.bin`) with `qnn-net-run` on the IQ8 HTP v75 | rc 0 in 0.86 s, output 1,105,920 bytes (1x108x2560 float32), bit-identical to the board's earlier recorded output (cosine 1.000000), 0 external aborts. The full six-batch WAV generation (host bridge, 7.8 GB of models) was not run |
| VSaaS (QNN path) | YOLOv8n ONNX -> `qairt-converter` -> `qairt-quantizer` (w8a16) -> `qnn-context-binary-generator` (v75) on the PC, `qnn-net-run` on the IQ8 | Works. Held-out `zidane.jpg`: 2 persons (0.87, 0.86) and a tie; `dog.jpg`: dog 0.31 (CPU 0.55). Recipe, numbers and pitfalls in `VSaaS/docs/EDGE_AI.md`. The repo's `yolov8_det_w8a8.dlc` needs an AI Hub token and was not available |
| LLM | llama.cpp b12803 win-arm64 (CPU and OpenCL/Adreno) with Qwen2.5-0.5B Q4_0, `run_llama_cpp.py` and `test_gemma4.py` | CPU about 20 tokens/s (CLI) and 38 (server), Adreno about 47. Fixed `.exe` lookup in `run_llama_cpp.py`. The Hexagon NPU path was **not** run: it needs the Hexagon SDK 6.7+, the OpenCL SDK and Windows test-signing (a host security change) |
| wake_word | Train, ONNX export, parity check and file-fed streaming with the stand-in keyword `marvin` | Runs. Found and fixed a train/inference feature mismatch (recall 3% -> 98% on held-out clips). Still a weak model; see `wake_word/README.md` |
| mojo-max-int | Mojo 0.26.1 and MAX 26.1 under WSL (aarch64) | `hello.mojo`, `agent.mojo` and `genie_client.mojo` compile and run (after porting to the current syntax); `max_graph_demo.mojo` does not compile on any release; versions pinned in the README |
| RoboAgent | Build of ExecuTorch with the QNN backend | **Not possible on this PC today:** the disk is 98% full (15 GB free), only VS 2019 Build Tools is installed (the setup needs VS 2022 with ARM64 and Clang), and there is no ExecuTorch checkout |

QAIRT 2.51 notes: the SDK's Python converter modules are x64, so on a Windows-on-Snapdragon PC use an x64 Python 3.10 venv with
`numpy==1.26.4 packaging==24.0 pandas==2.3.3 pyyaml==6.0.3 scipy==1.15.3 onnx==1.17.0`; the SDK's own `check-python-dependency`
fails on this platform because `opencv-python` has no ARM64 Windows wheel for its pin.
