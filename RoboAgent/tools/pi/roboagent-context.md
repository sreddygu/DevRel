# RoboAgent Context

RoboAgent is a Windows-on-Snapdragon ExecuTorch QNN playground. The local Gemma 4
model is served by `qnn_llm_host.exe` over `\\.\pipe\gemma4`.

The host keeps a continuous KV-cache conversation. Although the compiled model
has a theoretical 3,872-token usable capacity, the managed profile uses a
3,800-token runtime ceiling to avoid sequence-length assertions. Keep requests
concise. The managed launcher resets the host and replays bounded recent context
when the budget is exhausted; start a fresh Pi session if recovery reports an
error.

The first agent milestone is read-only code understanding. Do not modify files
or execute commands unless the user explicitly approves the Pi confirmation
dialog.
