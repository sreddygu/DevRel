# GesturDJ ACE-Step Architecture

GesturDJ uses a gesture layer to control an ACE-Step music-generation path.
Gesture recognition and live mixing remain separate from the offline music
generation workflow.

## ACE-Step music path

```text
gesture intent -> instrumental prompt -> host text preparation
-> ACE-Step DiT on IQ8 NPU -> host DCAE decode and vocoder -> WAV library
```

The current IQ8 deployment runs all 24 ACE-Step transformer blocks as six
chained four-block batches. Each batch must pass cosine similarity `>= 0.999`
against a saved reference before it is eligible for a WAV run.

## Supported operating envelope

- 10.031021-second audio duration.
- `1 x 108 x 2560` latent tensor.
- `1 x 6 x 2560` instrumental encoder condition.
- No lyrics or variable-length conditioning without a new exported and
  qualified context set.

## Developer references

- [`README.md`](README.md): project overview and latest output.
- [`ACE-Step/README.md`](ACE-Step/README.md): setup and generation commands.
- [`ACE-Step/IQ8_NPU_WAV_STATUS.md`](ACE-Step/IQ8_NPU_WAV_STATUS.md): numerical
  gates and safe resume procedure.
- [`blogs/ace-step-iq8-npu-deployment-guide.md`](blogs/ace-step-iq8-npu-deployment-guide.md): deployment
  narrative.

The legacy skill catalog remains available for gesture-development work. Its
music-model entries should be migrated to the ACE-Step workflow before being
used as operational guidance.
