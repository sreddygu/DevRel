---
name: library-generation-and-quality-evaluation
description: "Generate music clips in the background from style prompts with an on-device music model, then check each clip and the whole set with objective measurements such as loop seams."
version: 0.1.0
---

# Library Generation and Quality Evaluation

Back to the [GesturDJ README](../../README.md).

Fills the live mixer's clip library in the background. Generation takes minutes, so it never
sits on the live path. Gate the setup first with
[`npu-quantization-and-accuracy-gating`](../npu-quantization-and-accuracy-gating/SKILL.md).

## Generate

One clip per style prompt, using the mixed int8 setup in
[`diffrhythm_iq8_npu_int8_45s.ipynb`](../../diffrhythm_iq8_npu_int8_45s.ipynb) (cell for the song;
change `STYLE_PROMPT`). Lyrics: ascending `[mm:ss.xx]` lines, no empty lines, and the last line is
only an end marker (it is not sung). 16 steps takes about 5 minutes per 44.6 s clip.

## Evaluate

```
python diffrhythm_npu_scripts/evaluate_clip_library.py clip1.wav clip2.wav clip3.wav --out clip-library-report.json
```

| Check | Pass rule |
| --- | --- |
| Length | at least 20 s |
| Values | finite |
| Clipping | at most 0.1 percent of samples at full scale |
| Silence | at most 30 percent of 50 ms frames below -50 dBFS |
| DC offset | at most 0.01 |
| Library | one sample rate; loudness spread at most 8 dB so switching clips does not jump |

The start-to-end loudness difference is reported as loop seam (informational).

## Rules

- These checks find broken clips. They do not find bad music: a person listens.
- A failed clip is regenerated with another prompt or step count. The check is not removed.

## Measured (Qualcomm IQ8, mixed int8, 16 steps)

| Clip | Style prompt | Wall clock | NPU time | Checks |
| --- | --- | --- | --- | --- |
| 1 | acoustic folk, guitar, warm, gentle, female vocal. | about 5.7 min | about 80 s | pass |
| 2 | electronic, synth, upbeat, energetic, male vocal. | 9.9 min | 79.9 s | pass |
| 3 | ambient, pads, slow, dreamy, female vocal. | 12.2 min | 81.2 s | pass |

The library passes: 44.6 s each, loudness spread 3.3 dB. Loop seams are 3.9, 11.0 and 16.7 dB, so clips 2
and 3 would jump if looped; the mixer should crossfade or play them once. NPU time is steady; the
wall clock varies because the rest of the pipeline (text, style, audio decode) runs on the PC and was
slower while other jobs ran. Evidence: [`clip-library-report.json`](../../evidence/iq8-run/clip-library-report.json).

Complete when every clip and the library pass, or a failed clip is named.
