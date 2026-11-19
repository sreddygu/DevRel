# AURA on the IQ8 — Vision & Speech Deployment

**Status: ✅ verified on-device, 2026-08-11.** Milestone 1 (Eyes) runs on the
IQ8 **Hexagon NPU (HTP V75)**; Milestone 2 (Ears/Voice) runs on-device from
prebuilt aarch64 binaries. This is the reproducible runbook.

> For the **LLM/Brain (Milestone 4)** NPU bring-up — Genie / GenieX / the v75
> bundle blocker — see [`NPU_SETUP.md`](NPU_SETUP.md). This doc covers only
> vision + speech.

The on-device driver scripts referenced below live in the repo under
[`deploy/iq8/`](../deploy/iq8/) and are copied to the device as noted.

---

## Target device

| | |
|---|---|
| Board | `iq-8275-evk` (IQ8 EVK, VENTUNO-Q-class silicon) |
| OS | Qualcomm Linux Reference Distro (QLI) 2.0, glibc 2.43 |
| NPU | Hexagon HTP **V75** |
| CPU / RAM | 8 cores / 10 GiB |
| Address | `<device-ip>` (root / password auth) |
| Host key | `<host-key>` (SHA256 fingerprint from first connect) |
| Python | 3.14 with `numpy` + `cv2` (no `onnxruntime`/`PIL`); `dnf` present |
| QNN SDK | 2.47.1 under `/opt/qnn` (`qnn-net-run`, `libQnnHtp.so`, `libQnnModelDlc.so`, v75 dsp skels) |
| Audio | ALSA `arecord` / `aplay` present; no Python audio libs |

> **Note:** set `<device-ip>` to your board's address. SSH via PuTTY:
> `plink -ssh -batch -hostkey <HK> -pw <pw> root@<device-ip>`.

**No compiler / no pip on-device** — everything heavy is a prebuilt binary +
model file pushed over `scp`, mirroring the on-device pattern used for the LLM.

---

## 1. Vision → Hexagon NPU (HTP V75) ✅

YOLOv8 object detection on the NPU via `qnn-net-run` and a quantized DLC. No
Python ML wheels on-device — only `numpy`/`cv2` for image preprocessing.

### Artifacts (device paths under `/opt/aura-vision/`)

| Path | Source | Notes |
|---|---|---|
| `models/yolov8_det_w8a8.dlc` | VSaaS `models/yolov8_det_w8a8/` | YOLOv8 detector, INT8 weights+activations (w8a8) |
| `preprocess.py` | [`deploy/iq8/preprocess.py`](../deploy/iq8/preprocess.py) | image → NCHW float32 `input.raw` |
| `aura_npu_detect.py` | [`deploy/iq8/aura_npu_detect.py`](../deploy/iq8/aura_npu_detect.py) | full pipeline: preprocess → NPU → NMS → AURA Events |

### Deploy

```bash
HK=<host-key>   # SHA256 fingerprint shown on first connect
DEV=<device-ip>
plink -ssh -batch -hostkey $HK -pw <pw> root@$DEV "mkdir -p /opt/aura-vision/models /opt/aura-vision/data"
pscp -batch -hostkey $HK -pw <pw> <repo>/../VSaaS/models/yolov8_det_w8a8/yolov8_det_w8a8.dlc root@$DEV:/opt/aura-vision/models/
pscp -batch -hostkey $HK -pw <pw> deploy/iq8/aura_npu_detect.py                                 root@$DEV:/opt/aura-vision/
```

### Run

```bash
cd /opt/aura-vision
python3 aura_npu_detect.py data/bus.jpg
```

The raw `qnn-net-run` invocation (what `aura_npu_detect.py` shells out to):

```bash
export LD_LIBRARY_PATH=/opt/qnn/lib:/opt/qnn/dsp
export ADSP_LIBRARY_PATH=/opt/qnn/dsp
qnn-net-run --backend /opt/qnn/lib/libQnnHtp.so \
  --dlc_path /opt/aura-vision/models/yolov8_det_w8a8.dlc \
  --input_list input_list.txt --output_dir out   # input_list line: "images:=/abs/path/input.raw"
```

### Key finding — this DLC has a built-in decode head

Instead of the raw Ultralytics `(1, 84, 8400)` tensor, the w8a8 DLC emits **three
outputs** in `out/Result_0/`:

| File | Shape | Meaning |
|---|---|---|
| `boxes.raw` | `[8400, 4]` float32 | xyxy boxes in 640-input space |
| `scores.raw` | `[8400]` float32 | max class confidence per anchor |
| `class_idx.raw` | `[8400]` float32→int | argmax class id per anchor |

So on-device post-processing is only **threshold + NMS + scale-back** to
original pixels — no anchor decode needed. (Contrast with the PC path
`aura.vision.detector.decode_yolov8`, which decodes the raw tensor itself.)

### Result & caveats

- End-to-end **~1.35 s** per 640² frame on-device (graph finalize + NPU execute;
  fastrpc/CDSP confirmed in the logs).
- The **w8a8 model over-detects** (≈9 "person" on `bus.jpg` vs. 4 ground-truth)
  and reports **quantized confidence buckets**
  (0.44 / 0.5 / 0.56 / 0.62 / 0.67 / 0.72 / 0.77 / 0.81). The driver defaults to
  `conf=0.6` for a sane scene. A fresh **float or w8a16** export would tighten
  accuracy — the wiring is correct and model-agnostic.

---

## 2. Speech (STT + TTS) → on-device ✅

Both engines run from prebuilt **aarch64-Linux** binaries pulled directly onto
the device (it has its own internet link). CPU — no NPU STT/TTS artifacts exist
for v75, and whisper/piper are not the LLM, so CPU is appropriate.

### STT — whisper.cpp

| | |
|---|---|
| Binary | `whisper.cpp v1.9.2` → `whisper-bin-ubuntu-arm64.tar.gz` |
| Device path | `/opt/aura-speech/whisper-bin-ubuntu-arm64/` (`whisper-cli` + libs) |
| Model | `ggml-base.en.bin` (148 MB, HF `ggerganov/whisper.cpp`) |
| Driver | [`deploy/iq8/aura_stt.py`](../deploy/iq8/aura_stt.py) → `/opt/aura-speech/` |

```bash
# fetch (on-device, direct internet):
#   whisper-bin-ubuntu-arm64.tar.gz from github.com/ggml-org/whisper.cpp/releases/latest
#   ggml-base.en.bin from huggingface.co/ggerganov/whisper.cpp
cd /opt/aura-speech
python3 aura_stt.py jfk.wav
# raw form:
LD_LIBRARY_PATH=whisper-bin-ubuntu-arm64 \
  ./whisper-bin-ubuntu-arm64/whisper-cli -m ggml-base.en.bin -f jfk.wav -nt
```

Verified: perfect transcript of the canonical JFK sample.

### TTS — piper

| | |
|---|---|
| Binary | `piper` (release `2023.11.14-2`) → `piper_linux_aarch64.tar.gz` (bundles own `libonnxruntime.so` + espeak-ng) |
| Device path | `/opt/aura-speech/piper/` |
| Voice | `en_US-lessac-medium.onnx` (+`.json`, 63 MB, HF `rhasspy/piper-voices`) |
| Driver | [`deploy/iq8/aura_tts.py`](../deploy/iq8/aura_tts.py) → `/opt/aura-speech/` |

```bash
cd /opt/aura-speech
python3 aura_tts.py "AURA vision and speech are running on the IQ8."
# raw form:
echo "your text" | LD_LIBRARY_PATH=piper \
  ./piper/piper --model voices/en_US-lessac-medium.onnx --output_file out.wav
```

Real-time factor ≈ **0.19** (synthesis ~5× faster than audio duration). Playback
via ALSA `aplay`.

### Full round-trip

`jfk.wav` → whisper.cpp STT → text → piper TTS → `roundtrip.wav` — verified
end-to-end on the device.

---

## Mapping to the AURA package seam

The on-device drivers deliberately mirror the injectable-`backend` seam in the
package so the same `Event` contract flows through:

| PC (package) | IQ8 (driver) | Shared contract |
|---|---|---|
| `aura.vision.detector.Detector.detect` (onnxruntime, decodes raw tensor) | `deploy/iq8/aura_npu_detect.py` (`qnn-net-run`, decode-head DLC) | `Event(type="detection", entities=[label], source="vision", …)` |
| `aura.speech.stt.SpeechToText` (openai-whisper) | `deploy/iq8/aura_stt.py` (whisper.cpp) | `Event(type="speech", source="speech")` |
| `aura.speech.tts.TextToSpeech` (piper on PATH) | `deploy/iq8/aura_tts.py` (piper aarch64) | WAV bytes |

To run the package `Detector` against the NPU on a device that has QNN
onnxruntime EP, pass `providers=["QNNExecutionProvider"]`; the standalone driver
above is the wheel-free alternative for the current QLI image.

---

## Open item

The **LLM on the NPU** is still blocked (no v75 Genie bundle; all local bundles
are v73/X-Elite-locked). Vision (NPU) and speech (CPU) are done; closing the loop
end-to-end on-device needs the v75 LLM export — see [`NPU_SETUP.md`](NPU_SETUP.md).
