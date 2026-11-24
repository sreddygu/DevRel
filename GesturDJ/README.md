# GesturDJ: ACE-Step on IQ8 NPU

GesturDJ is now focused on **ACE-Step music generation on a Qualcomm IQ8 NPU**.
The ACE-Step DiT runs on the IQ8 as six chained, four-block context batches;
text preparation, DCAE decoding, and vocoding remain on the host.

## Latest validated output

- Output: `ACE-Step/data/outputs/ace_step_iq8_10s_27steps_seed20261119.wav`
- Audio: 10.031021 seconds, stereo, 48 kHz, 16-bit PCM
- Sampling: 27 steps, seed `20261119`, instrumental conditioning
- Backend: 24 ACE-Step DiT blocks execute on the IQ8 NPU
- Board health after the run: zero external-abort events

The demo uses the qualified fixed shape: a 10.031021-second latent and
six-token instrumental conditioning. This is an intentional constraint of the
current static NPU contexts.

## Start here

1. Read [`ACE-Step/README.md`](ACE-Step/README.md) for the supported workflow.
2. Read [`ACE-Step/IQ8_NPU_WAV_STATUS.md`](ACE-Step/IQ8_NPU_WAV_STATUS.md) for
   the evidence and numerical gates.
3. Follow [`ACE-Step/IQ8_SSH_RUNBOOK.md`](ACE-Step/IQ8_SSH_RUNBOOK.md) for the
   fail-closed WSL and SSH workflow.
4. Read [`blogs/ace-step-iq8-npu-deployment-guide.md`](blogs/ace-step-iq8-npu-deployment-guide.md)
   for the deployment architecture and supported workflow.
5. Read [`blogs/ace-step-iq8-npu-validation-guide.md`](blogs/ace-step-iq8-npu-validation-guide.md)
   for the numerical gates and operational validation process.

## Repository layout

- `ACE-Step/`: ACE-Step host integration, IQ8 contexts, runner, and documentation.
- `gesture_scripts/`: gesture-recognition and live-mixer utilities retained for
  future control integration.
- `skills/` and `skills-metadata/`: reusable project skills and metadata.

## Scope and safety

The IQ8 execution is gated. Every four-block batch must meet cosine similarity
`>= 0.999` against its saved reference before it is used in a WAV run. The
current NPU path is instrumental-only because the exported contexts require a
fixed six-token encoder condition. Do not add lyrics or variable-length text
without exporting and qualifying matching contexts first.
