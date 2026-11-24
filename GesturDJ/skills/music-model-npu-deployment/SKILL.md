---
name: music-model-npu-deployment
description: "Check that an IQ8 board is ready to run the DiffRhythm/ACE-Step music transformer on its NPU: OS image, NPU firmware, runtime libraries and compiled model graphs."
version: 0.1.0
---

# Music Model NPU Deployment

Back to the [GesturDJ README](../../README.md).

Use after `device-and-host-discovery` names an NPU board as the generator. The
supported model is ACE-Step, which runs all 24 DiT blocks as six chained
four-block batches. Follow [`ACE-Step/README.md`](../../ACE-Step/README.md) and
[`ACE-Step/IQ8_SSH_RUNBOOK.md`](../../ACE-Step/IQ8_SSH_RUNBOOK.md) to prepare the
board and host.

## Preflight (read-only)

On the board: OS and kernel; each remote processor state (`/sys/class/remoteproc/*`,
`cdsp` must say `running`); runtime libraries for the board's HTP version (here
v75); the ACE-Step server; each qualified context; external aborts since boot
(`dmesg`); and no stale server.

## Load check

Run the qualified ACE-Step smoke validation from
[`ACE-Step/README.md`](../../ACE-Step/README.md). The host-to-IQ8 bridge must
complete all six batches without an external abort.

## Measured (Qualcomm IQ8, HTP v75)

| Check | Result |
| --- | --- |
| Remote processors | adsp, gpdsp0, cdsp all running |
| External aborts since boot | 0 |
| ACE-Step NPU batches | 6 chained four-block batches |
| Stale server | none |
| Qualified cosine gate | at least 0.999 for every batch |

Evidence: [`ACE-Step/IQ8_NPU_WAV_STATUS.md`](../../ACE-Step/IQ8_NPU_WAV_STATUS.md).

## Rules

- Stop at the first failed check and name it.
- Never start a second server on a busy NPU. A hung call wedges the NPU until the board is rebooted; ask first.
- Binaries built for one HTP version do not load on another.
- The Ventuno Q uses the same Dragonwing IQ8 family on its product page. That is a reason to try, not a result.

Complete when the preflight is clean and all six batches complete, or a failed
check is named.
