# `deploy/iq8/` — on-device drivers for the IQ8

Wheel-free driver scripts that run AURA's perception on the **IQ8 EVK**
(QLI 2.0, Hexagon HTP V75). They shell out to prebuilt binaries already on the
device rather than importing the `aura` package, because the device image has no
compiler/pip and only `numpy`+`cv2` in its Python. Each emits the same `Event`
shape the package uses.

Full runbook (device paths, artifact sources, deploy commands, results):
[`../../docs/IQ8_DEPLOYMENT.md`](../../docs/IQ8_DEPLOYMENT.md).

| Script | Runs on | What it does |
|---|---|---|
| `preprocess.py` | CPU (cv2) | image → `640×640` NCHW float32 `input.raw` for `qnn-net-run` |
| `aura_npu_detect.py` | **Hexagon NPU** | image → YOLOv8 w8a8 DLC (`qnn-net-run`, HTP V75) → NMS → detection `Event`s |
| `aura_stt.py` | CPU | WAV → whisper.cpp `whisper-cli` → speech `Event` |
| `aura_tts.py` | CPU | text → piper (aarch64) → WAV (optional `aplay` playback) |

These are copied to `/opt/aura-vision/` (vision) and `/opt/aura-speech/`
(speech) on the device; the hard-coded paths at the top of each script assume
that layout. Model/binary artifacts are **not** committed here (sizes: DLC
3.8 MB, whisper model 148 MB, piper voice 63 MB) — see the runbook for their
sources and how they're fetched directly onto the device.
