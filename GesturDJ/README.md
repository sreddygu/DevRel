# GesturDJ

Gestures change music live. Two parts: an IMU gesture recognizer that runs on an Arduino Ventuno Q, and a song generator that runs DiffRhythm on the NPU of a Qualcomm IQ8 board. Around both sits a set of Synapse skills that a P3 developer (independent maker, hobbyist or student) can follow.

## Notebooks

- [`diffrhythm_iq8_npu_int8_45s.ipynb`](diffrhythm_iq8_npu_int8_45s.ipynb): **the demo.** Makes a 44.6 s song from a style prompt and lyrics, with the heavy part on the IQ8 NPU (mixed int8). Run it top to bottom: export, convert, quantize, compile, accuracy gate, song, play on the board. Documentation is inside the notebook.
- [`diffrhythm_iq8_npu_int8_45s.executed.ipynb`](diffrhythm_iq8_npu_int8_45s.executed.ipynb): the same notebook with its outputs from a full run, to read without a board.

## Documents

- [`DIFFRHYTHM_IQ8.md`](DIFFRHYTHM_IQ8.md): how the IQ8 NPU run works, board setup and the known memory-fault issue.
- [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md): status, measured results and the licensing note.
- [`GESTURDJ_SYNAPSE_SKILLS.md`](GESTURDJ_SYNAPSE_SKILLS.md): GesturDJ mapped onto the Synapse skill layers: summary, skills by layer, fuzzy areas, findings and open questions.

## Code

- [`diffrhythm_npu_scripts/`](diffrhythm_npu_scripts/): the scripts the notebook calls. See its [`README.md`](diffrhythm_npu_scripts/README.md).
- [`gesture_scripts/`](gesture_scripts/): the IMU gesture recognizer (train, ONNX export, ONNX Runtime inference). See its [`README.md`](gesture_scripts/README.md) and [`ventunoq.md`](gesture_scripts/ventunoq.md) for running it on the Ventuno Q.

## Skills

The catalog is in [`skills/README.md`](skills/README.md); check it with `python skills/validate_skills.py`. The tool list is [`skills/mcp-tools.yaml`](skills/mcp-tools.yaml).

| Layer | Skill |
| --- | --- |
| Agent | [`gesturdj-agent`](skills/gesturdj-agent/SKILL.md) |
| Journey | [`gesturdj-build-journey`](skills/gesturdj-build-journey/SKILL.md) |
| Domain | [`device-and-host-discovery`](skills/device-and-host-discovery/SKILL.md) |
| Domain | [`gesture-dataset-preparation`](skills/gesture-dataset-preparation/SKILL.md) |
| Domain | [`gesture-model-training-and-evaluation`](skills/gesture-model-training-and-evaluation/SKILL.md) |
| Domain | [`model-export-and-deployment`](skills/model-export-and-deployment/SKILL.md) |
| Domain | [`on-device-gesture-validation`](skills/on-device-gesture-validation/SKILL.md) |
| Domain | [`gesture-to-live-mix-design`](skills/gesture-to-live-mix-design/SKILL.md) |
| Domain | [`audio-output-integration`](skills/audio-output-integration/SKILL.md) |
| Domain | [`live-mixer-and-latency-validation`](skills/live-mixer-and-latency-validation/SKILL.md) |
| Domain | [`music-model-npu-deployment`](skills/music-model-npu-deployment/SKILL.md) |
| Domain | [`npu-quantization-and-accuracy-gating`](skills/npu-quantization-and-accuracy-gating/SKILL.md) |
| Domain | [`library-generation-and-quality-evaluation`](skills/library-generation-and-quality-evaluation/SKILL.md) |
| Context | [`gesture-event-contract`](skills/gesture-event-contract/SKILL.md) |
| Context | [`p3-self-service-boundaries`](skills/p3-self-service-boundaries/SKILL.md) |

## Evidence

[`evidence/pc-run/`](evidence/pc-run/): logs and JSON from the PC test run that the skills cite.
[`evidence/iq8-run/`](evidence/iq8-run/): the board probe, on-device validation, cross-machine parity, the live-mixer replay and the [agent run log](evidence/iq8-run/agent-run-log.md) from a Qualcomm IQ8 board.

## License check before you demo

DiffRhythm is three licenses in one pipeline. Check each before you show it to anyone outside the team. This is a summary, not legal advice.

### DiffRhythm DiT checkpoints

| Checkpoint | Used by the IQ8 demo? | Model distinction | License evidence | DiT license |
| --- | --- | --- | --- | --- |
| [`ASLP-lab/DiffRhythm-1_2`](https://huggingface.co/ASLP-lab/DiffRhythm-1_2) (`cfm_model.pt`) | **Yes** | Versioned checkpoint used by the exporter; its published 16-block, 1B configuration matches Base, but the checkpoint weights are a different file. | Repository [`LICENSE`](https://huggingface.co/ASLP-lab/DiffRhythm-1_2/blob/main/LICENSE) | Apache-2.0 file supplied; obtain legal review before relying on it in a product. |
| [`ASLP-lab/DiffRhythm-base`](https://huggingface.co/ASLP-lab/DiffRhythm-base) | No | Documented Base checkpoint for roughly 95-second songs; same published 16-block, 1B configuration as `1_2`, but different checkpoint weights. | Current repository metadata says Apache-2.0, but older `README.md` and `LICENSE.md` artifacts refer to the Stability license. | **Conflicting published artifacts; obtain written clarification from the publisher before relying on it.** |

This table covers the DiT checkpoints only. `DiffRhythm-1_2` is the checkpoint loaded by the IQ8 exporter; it is not `DiffRhythm-base`. Neither checkpoint makes the complete DiffRhythm audio pipeline Apache-only: it still needs the VAE to decode latents to audio and the style encoder for style conditioning. Because the weights differ, do not substitute Base into the existing IQ8 artifacts: re-export ONNX, rebuild the NPU graphs, and rerun the accuracy gate first. The VAE and style encoder below have separate terms.

| Piece | License | What it means for a demo |
| --- | --- | --- |
| DiffRhythm code and selected DiT weights | Apache-2.0 | Free to use, modify and publish. See the checkpoint table above. |
| VAE (`DiffRhythm-vae`) | Stability AI Community License | Free for non-commercial use. Commercial use is gated by company revenue, so a large company needs an agreement with Stability. Check the current terms at stability.ai/license. |
| MuQ-MuLan style-encoder weights | CC-BY-NC-4.0 | Non-commercial only: evaluation, research, internal use. |

**Internal or closed-door demo** (team reviews, evaluation): go ahead.

**Public, customer-facing or event demo:** get legal sign-off first. A promotional demo can count as commercial use even when nothing is sold. Label it as an evaluation, not a product path.

**Do not redistribute the MuQ-MuLan or VAE weights.** Point readers to their original sources, which is how our notebook gets them.

**If legal says no:** swap the model (ACE-Step's code and weights are Apache-2.0; in our listening it fell short of what a demo needs), or ask the DiffRhythm authors (ASLP lab) for permission to use the style encoder commercially. Either costs time, so ask early if the demo has a date.

Label all generated output as AI-generated.

## Before you run the notebook

Set `IQ8_HOST`, `IQ8_HOSTKEY` and `QLI_SSH_PASSWORD` in the environment, in the terminal you start VS Code or Jupyter from. Nothing is stored in files. Generated songs go to `diffrhythm_outputs/` (created on first run, not checked in).
