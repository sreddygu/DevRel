---
name: quad-deploy
description: Use when the user asks to "deploy a model to my Android phone", "push to Arduino", "deploy to Snapdragon target", or invokes /quad-deploy. Walks through deploy.sh + remote profiling.
trigger: "deploy"
---

# QUAD Deployment Skill

Push a converted model + runtime libraries to a target device and
optionally run inference there.

## Pre-flight

1. Confirm the target type:
   - **Android** — needs `adb devices` to show the device, plus
     `ANDROID_SERIAL` env var if multiple devices are connected
   - **Linux (SSH)** — needs `TARGET_IP`, `TARGET_USER`, optional
     `TARGET_SSH_KEY` env vars; SSH must be reachable
   - **Local** — model stays on this machine, just runs locally

2. Run `quad doctor --real-mode` to verify the SDK + toolchain.
   Block deployment if it fails.

## Steps

1. **Convert** the model first if it's not already a .dlc / .bin:
   - Call `quad-convert` skill, then return here.

2. **Choose Hexagon version** for the target:
   - QCS2210 (Arduino UNO Q): v66
   - Snapdragon 8 Gen 3: v75
   - Snapdragon 8 Elite: v79
   - Snapdragon X Elite: v75 (HTP)

3. **Run deploy.sh** via the Bash tool:
   ```
   ./deploy.sh path/to/model.dlc \
     --target-ip 192.168.1.50 \
     --target-user root \
     --hexagon-version v66 \
     --runtime --use_dsp
   ```

4. **Watch the output** for the four steps:
   - Step 1: Convert (skipped if already DLC)
   - Step 2: Deploy (scp the model + skel libs)
   - Step 3: Execute (snpe-net-run on target)
   - Step 4: Retrieve (scp outputs back)

5. **Surface failures** clearly:
   - Connection refused → SSH config issue
   - "skel not found" → wrong Hexagon version, look at
     `src/quad/adapters/dsp_env.py` for the lookup table
   - "transportStatus: 9 / 0x80000406" on Windows targets — DSP
     signature mismatch, see `docs/REAL_HARDWARE.md`

## Limitations to call out

- `deploy.sh` is currently SNPE-only (no QNN backend support yet —
  GAP_ANALYSIS T3.5)
- Target detection of skel naming is somewhat fragile for older
  Hexagon versions
- No rollback / versioning support — manual cleanup required

## After deployment

- Profile remotely: `quad-profile` against the deployed model path
- Generate Android Kotlin / JNI code via `quad-codegen` and bundle
  into your app
- Set up CI by templating these commands in `.github/workflows/`
