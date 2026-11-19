---
name: roboagent-qnn
description: Run and troubleshoot the local RoboAgent Gemma 4 ExecuTorch QNN host on Windows-on-Snapdragon.
---

# RoboAgent QNN

- Start the managed runtime with `tools/pi/start-roboagent-pi.ps1`.
- The model is `roboagent/gemma4` and the named pipe is `\\.\pipe\gemma4`.
- If the pipe is missing, verify the host printed `Listening on` before debugging Pi.
- Keep prompts short because the managed Gemma profile uses a 3,800-token QNN
  context ceiling. The compiled model's theoretical usable capacity is 3,872
  tokens, but the launcher reserves headroom for reliable operation.
- Never put QNN SDK paths, credentials, or tokens into notes or model prompts.
