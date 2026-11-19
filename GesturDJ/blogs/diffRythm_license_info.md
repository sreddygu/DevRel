# DiffRhythm: components, checkpoints, and licensing notes

> **Status:** working notes for GesturDJ. This is not legal advice; obtain legal review before a public, customer-facing, or commercial demo.

## The pipeline

DiffRhythm is an end-to-end pipeline rather than a single model.

| Component | What it takes in | What it produces | Why it is needed |
| --- | --- | --- | --- |
| **MuQ-MuLan** | A style prompt, such as “warm acoustic folk, gentle female vocal” | A compact style embedding | Tells the generator what the music should sound like: genre, mood, instrumentation, and vocal character. |
| **DiffRhythm DiT** | Lyrics/timing, the style embedding, and diffusion noise | Audio latents | The core generative model. It iteratively denoises a compact song representation. GesturDJ runs this heavy component on the IQ8 NPU. |
| **DiffRhythm VAE** | Final audio latents | A playable waveform/WAV | Converts the DiT’s compressed latent representation back into actual audio samples. |

The DiT output is a latent tensor, not audio. In GesturDJ it is shaped like `[batch, latent_frames, 64]`; the VAE is therefore required to produce a WAV file.

```text
Lyrics + style prompt
        |
        +-- MuQ-MuLan on PC --> style embedding
        |
        +-- DiffRhythm DiT on IQ8 NPU --> audio latents
        |
        +-- DiffRhythm VAE on PC --> WAV audio
```

## Checkpoint selection and licensing

| Checkpoint | Used by GesturDJ's IQ8 exporter? | Model distinction | Published license position |
| --- | --- | --- | --- |
| [`ASLP-lab/DiffRhythm-1_2`](https://huggingface.co/ASLP-lab/DiffRhythm-1_2), `cfm_model.pt` | **Yes** | Versioned checkpoint used by `export_segments.py`. Its published 16-block, 1B configuration matches Base, but its weights are a different file. | The repository supplies an [Apache-2.0 `LICENSE`](https://huggingface.co/ASLP-lab/DiffRhythm-1_2/blob/main/LICENSE). Obtain legal review before relying on it in a product. |
| [`ASLP-lab/DiffRhythm-base`](https://huggingface.co/ASLP-lab/DiffRhythm-base) | No | Documented Base checkpoint for roughly 95-second songs; same published 16-block, 1B configuration as `1_2`, but different weights. | Current repository metadata says Apache-2.0, while older published README/license artifacts refer to the Stability license. Obtain written clarification from the publisher before relying on it. |

GesturDJ loads `ASLP-lab/DiffRhythm-1_2` and `cfm_model.pt` in [`diffrhythm_npu_scripts/export_segments.py`](../diffrhythm_npu_scripts/export_segments.py). Do not substitute Base into existing IQ8 artifacts: re-export ONNX, rebuild the NPU graphs, and rerun the accuracy gate.

## Why changing the DiT does not make the full pipeline Apache-only

Changing only the DiT checkpoint does not remove the other two components:

| Component | Project-documented license position | Consequence |
| --- | --- | --- |
| DiffRhythm DiT/code | Apache-2.0 evidence for the selected `DiffRhythm-1_2` repository | This alone does not make the assembled audio-generation pipeline license-clean. |
| `DiffRhythm-vae` | Stability AI Community License | Needed to decode latents to playable audio. |
| MuQ-MuLan weights | CC-BY-NC-4.0 | Used to convert a text style prompt to the style embedding; non-commercial terms remain relevant. |

## Gestures as a replacement for MuQ-MuLan

A camera or Modulino gesture recognizer can replace MuQ-MuLan **at runtime** only if it produces the style-conditioning vector the DiT expects. GesturDJ exports a `style_prompt` input shaped `[1, 512]`.

```text
Camera or Modulino gesture
        -> gesture recognizer
        -> gesture-to-style mapping or learned adapter
        -> 512-value style embedding
        -> DiffRhythm DiT
        -> VAE
        -> WAV
```

Practical options:

1. Map each gesture class to a fixed, precomputed 512-value embedding. This removes MuQ-MuLan from runtime but needs legal review if the embeddings were derived from MuQ-MuLan.
2. Train a small gesture-to-embedding adapter. It must produce an embedding compatible with the DiT's training distribution.
3. Fine-tune/retrain DiffRhythm to condition directly on gesture features. This is the most robust approach, but it is a model-development project.

Removing the VAE is different: without a compatible decoder, the output remains latents and cannot be played as a song.

## Decision summary

- Keep the current `DiffRhythm-1_2` setup to reproduce the existing IQ8 demo.
- Do not switch to `DiffRhythm-base` expecting the complete pipeline to become Apache-only.
- A DiT-only technical notebook is possible, but it produces latents rather than audio.
- An end-to-end Apache-only song generator needs permissively licensed replacements for the VAE and style encoder, or a different model stack.
