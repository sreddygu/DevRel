# Project Context

GesturDJ is an ACE-Step IQ8 NPU project. The working path runs the 24-block
ACE-Step DiT through six persistent bounded batches on IQ8. The host handles
text setup, DCAE decode, and vocoding.

## Current baseline

- Fixed latent shape: `1 x 108 x 2560` (10.031021 seconds).
- Fixed encoder shape: `1 x 6 x 2560` (instrumental conditioning).
- Numerical gate: cosine `>= 0.999` for every batch.
- Latest high-quality output: `ACE-Step/data/outputs/ace_step_iq8_10s_27steps_seed20261119.wav`.

Read [`ACE-Step/IQ8_NPU_WAV_STATUS.md`](ACE-Step/IQ8_NPU_WAV_STATUS.md) before
changing exports, graph contexts, or sampling settings.
