# IQ9 AURA E2E Resume State

Saved on September 23, 2026. The device was unavailable during the final
recheck, so the results below are the last verified state from September 22,
2026.

## Target

```text
Device: Dragonwing IQ-9075 EVK
Last known IP: 192.168.29.185
Camera: ZEB LIVE PRO
Video stream: /dev/video28
Metadata-only node: /dev/video29
Microphone: plughw:0,0
Speaker: plughw:1,0
```

Do not store device credentials in this repository or this document.

## Last Verified Runtime State

GenieX was installed and configured as follows:

```text
GenieX CLI: v0.7.0
QAIRT runtime: 2.45
HTP architecture: v73
Model: qualcomm/Gemma-4-E4B-it:W4A16
Model cache: /opt/geniex-data
Server endpoint: http://0.0.0.0:18181
```

The persistent systemd service was enabled and running:

```text
/etc/systemd/system/aura-geniex.service
/opt/aura-iq9/start_geniex_server.sh
```

Local source files:

```text
deploy/iq9/aura-geniex.service
deploy/iq9/start_geniex_server.sh
```

## Deployed AURA Files

```text
/opt/aura/src/aura
/opt/aura/deploy/aura_e2e.py
/opt/aura/deploy/aura_live.py
/opt/aura-vision/aura_npu_detect.py
/opt/aura-speech/aura_stt.py
/opt/aura-speech/aura_tts.py
```

## Verified E2E Use Cases

### Gemma on IQ9 NPU

- Direct GenieX inference detected HTP v73.
- Generation speed was approximately 8.8 tokens/second.
- `/v1/models` returned `qualcomm/Gemma-4-E4B-it:W4A16`.
- AURA's real `LocalLLM` client returned `FINAL_OK` through the IQ9 endpoint.

### USB Camera

- `/dev/video28` opened successfully through OpenCV V4L2.
- Frames were captured at 640 x 480.
- `/dev/video29` was confirmed to be UVC metadata, not a video stream.

### Vision on HTP

- The deployed YOLOv8 W8A8 DLC executed successfully through `qnn-net-run` and
  `libQnnHtp.so` on IQ9.
- Empty-room scenario at confidence 0.75 produced `nothing` during the final
  scripted run.
- The canonical positive image produced five person detections at confidence
  0.75.

### Speech

- Whisper STT transcribed the bundled JFK WAV correctly.
- Piper generated valid WAV output.
- Playback through `plughw:1,0` completed with exit code 0.
- The USB camera microphone captured from `plughw:0,0`.
- An automated speaker-to-microphone loop transcribed:
  `What do you see right now? What is he right now?`

### Memory and Reasoning

- Detection and speech events persisted to SQLite.
- `where_is("bus")` returned `living room` in the low-threshold canonical bus
  scenario.
- Gemma answered current-scene and remembered-object questions through the
  native OpenAI-compatible GenieX server.

### Actions

- No-person branch: `set_light(porch, OFF)` with
  `porch light OFF - no person detected`.
- Person-present branch: `set_light(porch, ON)` with the detected person count.
- Both actions were written back to memory as action events.

### Live Interactive Loop

The following paths were exercised:

- `look`: capture a fresh USB-camera frame and run YOLO.
- Typed question: camera -> memory -> Gemma -> Piper -> speaker.
- Remembered-object question: Gemma reported the stored bus location.
- Voice question: USB mic -> Whisper -> camera -> Gemma -> Piper.

## Code Changes Saved Locally

`deploy/iq8/aura_live.py` now:

- accepts `AURA_CAMERA`, including camera index `28`;
- grounds Gemma with the current scene plus remembered detections;
- accepts `AURA_VISION_CONF`, defaulting to `0.75`;
- reports the configured camera in its startup banner.

`deploy/iq8/aura_e2e.py` now:

- accepts an isolated `AURA_DB` path;
- accepts `AURA_VISION_CONF`, defaulting to `0.75`;
- reports `nothing` for an empty scene;
- correctly reports the light OFF branch.

`tests/test_deploy_e2e.py` covers both light-action branches. The focused test
run passed:

```text
2 passed
```

The full project test suite was started but interrupted before completion. Run
it again when resuming.

## Known Vision Limitation

The current IQ8-origin W8A8 DLC is executable on QCS9075 HTP v73 but is not
reliably accurate on the live IQ9 camera. Empty-room frames intermittently
produced dog or cat detections with confidence as high as 0.809. Raising the
threshold above that also removes the valid 0.809 person detections from the
canonical positive image.

Confidence 0.75 reduces false positives but does not eliminate them. Treat the
current vision result as an integration demonstration, not production-quality
occupancy detection. The next vision task is a QCS9075-targeted model or a
second-stage verification strategy.

## Resume Checklist

1. Confirm the current IQ9 IP and SSH availability.
2. Verify the persistent model service:

   ```bash
   systemctl is-enabled aura-geniex.service
   systemctl is-active aura-geniex.service
   systemctl --no-pager status aura-geniex.service
   curl http://127.0.0.1:18181/v1/models
   ```

3. Verify the camera and audio devices:

   ```bash
   v4l2-ctl --list-devices
   v4l2-ctl -d /dev/video28 --list-formats-ext
   arecord -l
   aplay -l
   ```

4. Redeploy the latest scripts if needed:

   ```text
   deploy/iq8/aura_e2e.py -> /opt/aura/deploy/aura_e2e.py
   deploy/iq8/aura_live.py -> /opt/aura/deploy/aura_live.py
   ```

5. Run the focused local regression test:

   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests\test_deploy_e2e.py -q
   ```

6. Rerun the full local test suite:

   ```powershell
   .\.venv\Scripts\python.exe -m pytest -q
   ```

7. Run a live IQ9 turn:

   ```bash
   PYTHONPATH=/opt/aura/src:/opt/aura-vision:/opt/aura-speech \
   AURA_CAMERA=28 \
   AURA_MIC=plughw:0,0 \
   AURA_SPK=plughw:1,0 \
   AURA_VISION_CONF=0.75 \
   AURA_LLM_BASE_URL=http://127.0.0.1:18181 \
   AURA_LLM_MODEL='qualcomm/Gemma-4-E4B-it:W4A16' \
   python3 /opt/aura/deploy/aura_live.py
   ```

