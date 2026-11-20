# ACE-Step IQ8 NPU WAV Status

Last updated: November 20, 2026.

## Working end-to-end path

The ACE-Step DiT now runs end-to-end on the IQ8 NPU. `iq8_npu_bridge.py`
dispatches live tensors through six chained persistent-server batches:

| Blocks | Final cosine | Result |
| --- | ---: | --- |
| 0-3 | 0.9999539421 | pass |
| 4-7 | 0.9998565466 | pass |
| 8-11 | 0.9998298288 | pass |
| 12-15 | 0.9997063599 | pass |
| 16-19 | 0.9997924376 | pass |
| 20-23, replacement block 22 | 0.9999190429 | pass |

Block 22 uses the scale-32 replacement context. Its single-block IQ8 gate is
`0.9999998830` cosine.

## Generated WAVs

| File | Steps | Seed | Result |
| --- | ---: | ---: | --- |
| `data/outputs/ace_step_iq8_10s_4steps_seed20261120.wav` | 4 | 20261120 | Smoke validation. |
| `data/outputs/ace_step_iq8_10s_27steps_seed20261120.wav` | 27 | 20261120 | Current quality baseline. |

Both files are 10.031021-second stereo 48 kHz 16-bit PCM WAVs. The 27-step
run completed in 552.8 seconds with zero IQ8 external-abort events.

## Current contract

- DiT input: `hidden_states` shape `1 x 108 x 2560`.
- Encoder condition: shape `1 x 6 x 2560`.
- Supported duration: exactly `10.031021` seconds.
- Supported condition: instrumental (`--lyrics ''`) with guidance scale `1.0`.
- Host stages: text preparation, DCAE decode, vocoder.
- IQ8 stages: all 24 DiT blocks, for every denoising step.

The bridge fails closed on a tensor-size mismatch. Lyrics and variable-length
prompt conditions are unsupported until matching static contexts are exported
and qualified.

## Resume safely

1. Check `dmesg | grep -c 'external abort'` after connecting to the board.
2. Stop if SSH fails, a stale NPU runner exists, or an abort count is nonzero.
3. Keep the replacement block-22 context at
   `/root/ace_step_iq8_block22_scaled32/ctx/block22_scaled32.bin`.
4. Use 27 steps for quality runs and a new output filename for each seed.
5. Validate the WAV header and board health after every long run.
