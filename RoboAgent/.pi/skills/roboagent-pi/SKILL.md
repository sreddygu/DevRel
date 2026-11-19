---
name: roboagent-pi
description: Use Pi with the local RoboAgent Gemma 4 provider and safe workspace tools.
---

# RoboAgent Pi

- Use the managed launcher instead of starting the host manually when possible.
- Read-only tools are preferred: `read_file`, `list_directory`, `search_files`, and Git inspection.
- Ask for confirmation before enabling or using mutation tools.
- Ground answers in files retrieved through tools rather than guessing.
- Let the managed launcher recover the host when the QNN context is exhausted.
  Restart Pi and the host only if recovery reports an error; inspect
  `logs\host-recovery-gemma4.log` first.
