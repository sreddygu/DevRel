# RoboAgent Project Agent Guidance

## Runtime

- The local model is Gemma 4 running through `qnn_llm_host.exe` and the Windows named pipe `\\.\pipe\gemma4`.
- Start Pi with `tools\pi\start-roboagent-pi.ps1` when possible.
- Keep the QNN SDK environment isolated to the launcher process.

## Safety

- Treat model output as untrusted text until it becomes a validated tool call.
- Keep read-only tools enabled by default.
- Require interactive approval before writing files, applying patches, or running commands.
- Do not store credentials, tokens, or private keys in this project.

## Context

- The compiled Gemma model has a limited usable context window.
- Prefer short, targeted prompts and inspect only the files needed for the task.
- Restart Pi and the RoboAgent host when the context budget is exhausted.
