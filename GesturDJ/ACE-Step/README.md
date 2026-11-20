# ACE-Step on IQ8 NPU

This directory contains the supported ACE-Step music-generation path for the
Qualcomm IQ8. The host runs text preparation, DCAE decoding, and vocoding; the
IQ8 runs all 24 DiT blocks as six chained four-block batches.

## Validated configuration

| Setting | Value |
| --- | --- |
| Latent shape | `1 x 108 x 2560` |
| Audio duration | `10.031021` seconds |
| Encoder shape | `1 x 6 x 2560` |
| Conditioning | Instrumental only |
| IQ8 gate | Cosine `>= 0.999` |
| Latest long run | 27 sampler steps, seed `20261119` |

The static IQ8 contexts do not accept lyrics or arbitrary encoder lengths.
The runner fails closed when a live tensor differs from the qualified contract.

## Generate a WAV from WSL

Use the qualified instrumental prompt and shape. Start an authenticated WSL
ControlMaster session as documented in `IQ8_SSH_RUNBOOK.md`; do not save board
credentials in files or source code. The 27-step setting is the quality
baseline; use four steps only for a fast integration check.

```bash
cd /mnt/c/Dropbox/DevRel/academy/GesturDJ/ACE-Step
export IQ8_HOST='<board address>'

data/iq8/runner/run_iq8_controlmaster_wav.sh \
  data/outputs/ace_step_iq8_10s_27steps_seed20261120.wav \
  27 \
  20261120
```

## Core files

- `data/src/acestep/iq8_npu_bridge.py`: live host-to-IQ8 tensor bridge.
- `data/iq8/runner/ace_step_iq8_infer.py`: host orchestration and WAV writer.
- `data/iq8/runner/run_iq8_controlmaster_wav.sh`: authenticated WSL launcher.
- `IQ8_NPU_WAV_STATUS.md`: results and safe resume notes.

## Before changing anything

Re-exporting an ACE-Step block, changing the NPU graph lifecycle, using lyrics,
or changing tensor shapes invalidates the current qualification. Regenerate the
matching contexts and repeat the full six-batch cosine gate first.
