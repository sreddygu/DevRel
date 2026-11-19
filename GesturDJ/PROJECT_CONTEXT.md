# Project Context

Back to the [GesturDJ README](README.md).

The demo is [`diffrhythm_iq8_npu_int8_45s.ipynb`](diffrhythm_iq8_npu_int8_45s.ipynb); background is in [`DIFFRHYTHM_IQ8.md`](DIFFRHYTHM_IQ8.md).

## Goal and status

Run DiffRhythm song generation on a Qualcomm NPU. Done: the DiT runs on the IQ8 NPU (HTP v75) as four chained 4-block graphs through a persistent C++ runner (`dit_server`). Segments 1 and 2 run as W8A16 int8, segments 0 and 3 stay fp16 (all-int8 fails the accuracy gate, cosine 0.61).

## Measured (IQ8, 16 sampler steps, 44.6 s song = 960 frames)

- NPU: 2.5 s per pass (3.7 s fp16), 81 s per song. Gate cosine vs fp32: 0.99986 mixed, 0.99999 fp16.
- Whole song cell: about 4 min on a quiet PC, typically about 6 min; the spread is PC-side work (encoders, decoder), not the NPU.
- For comparison, the stock 95 s song: NPU 194 s per song, about 10 to 13 min total.
- Board stability: 45 s mixed, 45 s fp16 and 95 s mixed loaded 6 times each with no reset; the stock 95 s fp16 graphs reset the board 2 of 2 times.
- Sound quality of a 45 s song is not formally judged (model trained on 95 s). Lyrics: DiffRhythm does not sing the last line.

## Caveats

- DiffRhythm code is Apache-2.0; the VAE is under the Stability AI Community License; MuQ-MuLan weights are CC-BY-NC-4.0 (evaluation only). Complete a licensing review before any product use or external demo; see [License check before you demo](README.md#license-check-before-you-demo).
- The IQ8 board has a memory fault that can reset it while loading big graphs (see [`DIFFRHYTHM_IQ8.md`](DIFFRHYTHM_IQ8.md)).
- No passwords, tokens or keys in project files; scripts read them from env vars.
- Keep model downloads in WSL, not the nearly full Windows `C:` drive.
