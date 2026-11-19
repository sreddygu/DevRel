# Device and Host Discovery

Back to the [GesturDJ README](../../README.md).

Use this skill first, before training, deploying or generating anything. It
answers: *what hardware does this developer actually have, and where should each
GesturDJ stage run?*

## Probe (read-only)

1. **Host (local machine):** run `python gesture_scripts/discover_host.py --out
   device-profile.json` with the Python you will use. It reports OS, the **real**
   CPU architecture (an x64 Python on an ARM64 PC says `AMD64` everywhere else, so
   it asks Windows), Python version, free disk, versions of numpy, scikit-learn,
   joblib, torch, onnx, onnxruntime, and audio players on PATH. Packages it lists
   as missing become the install list (note: `onnx` and `onnxscript` are needed to
   export).
2. **Sensor / recognizer board (for example Arduino Ventuno Q):** over SSH, `uname -m`,
   `/etc/os-release`, `python3 --version`, whether `onnxruntime` imports,
   `ls /dev/video*` (camera), `aplay -l` (audio sink). **Never import `torch` on the
   board** (it can crash with an illegal instruction); the recognizer runs on
   ONNX Runtime.
   `discover_host.py` only probes the machine it runs on, so these board fields
   stay `unknown` until this SSH probe is run. A board image may have no `pip` or
   `venv`; if so, ship wheels from the PC, or copy the missing pure-Python standard-library modules from CPython source (see the IQ8 findings in the design document).
3. **Generator device (optional):** a board with an NPU capable of the music model,
   observed the same way.
4. **Fallback:** if no generator device exists or the developer does not own one,
   the generator stage is placed on the PC (CPU).

## Output: [`device-profile.json`](../../evidence/pc-run/device-profile.json)

```json
{
  "host": {"os": "...", "arch": "...", "python": "...", "onnxruntime": "present|missing|unknown", "free_disk_gb": 0},
  "recognizer_board": {"reachable": true, "arch": "...", "os": "...", "python": "...", "onnxruntime": "...", "camera": "present|absent|unknown", "audio_sink": "present|absent|unknown"},
  "generator": {"where": "npu_board|pc_cpu|none", "reason": "..."},
  "placement": {"sensing": "...", "recognition": "...", "mixing": "...", "generation": "...", "playback": "..."},
  "unknown": ["fields not observed"]
}
```

Rules: record only what was observed; mark everything else `unknown`; if a stage
has no capable device, say so and name the fallback. This skill is complete when
the profile is written and every placement has a reason. It does not install
anything, validate models or measure latency.
