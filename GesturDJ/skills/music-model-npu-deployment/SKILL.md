---
name: music-model-npu-deployment
description: "Check that an IQ8 board is ready to run the DiffRhythm/ACE-Step music transformer on its NPU: OS image, NPU firmware, runtime libraries and compiled model graphs."
version: 0.1.0
---

# Music Model NPU Deployment

Back to the [GesturDJ README](../../README.md).

Use after `device-and-host-discovery` names an NPU board as the generator. The model is the
DiffRhythm transformer split into four chained graphs; how it is built is in
[`DIFFRHYTHM_IQ8.md`](../../DIFFRHYTHM_IQ8.md) and the demo notebook
[`diffrhythm_iq8_npu_int8_45s.ipynb`](../../diffrhythm_iq8_npu_int8_45s.ipynb). This skill checks
that a board is ready and the graphs load.

## Preflight (read-only)

On the board: OS and kernel; each remote processor state (`/sys/class/remoteproc/*`, `cdsp` must say
`running`); runtime libraries for the board's HTP version (here v75); the `dit_server` binary;
each context folder has four `segN.bin` files with their `segN.ok` markers; external aborts since boot
(`dmesg`); and no `dit_server` already running.

## Load check

Run the fixed test case through the four graphs ([`gate_board.py`](../../diffrhythm_npu_scripts/gate_board.py)).
Two passes must complete.

## Measured (Qualcomm IQ8, HTP v75)

| Check | Result |
| --- | --- |
| Remote processors | adsp, gpdsp0, cdsp all running |
| External aborts since boot | 0 |
| fp16 binaries | 4 of 4 with markers, 2151 MB |
| int8 (w8a16) binaries | 4 of 4 with markers, 1098 MB |
| Stale server | none |
| fp16 graphs | load 3.9 s, pass 3.7 s |
| Mixed graphs | load 2.2 s, pass 2.5 s |

Evidence: [`npu-deployment-preflight.txt`](../../evidence/iq8-run/npu-deployment-preflight.txt),
[`npu-accuracy-gate.log`](../../evidence/iq8-run/npu-accuracy-gate.log).

## Rules

- Stop at the first failed check and name it.
- Never start a second server on a busy NPU. A hung call wedges the NPU until the board is rebooted; ask first.
- Binaries built for one HTP version do not load on another.
- The Ventuno Q uses the same Dragonwing IQ8 family on its product page. That is a reason to try, not a result.

Complete when the preflight is clean and two passes ran, or a failed check is named.
