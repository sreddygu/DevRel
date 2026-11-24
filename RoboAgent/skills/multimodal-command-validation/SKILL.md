---
name: multimodal-command-validation
description: "Evaluate the responses and proposed tool calls of RoboAgent (a local Gemma 4 robot assistant running on Windows on Snapdragon) with deterministic, grounded checks."
version: 0.1.0
---

# RoboAgent Multimodal Command Validation

Evaluate a local RoboAgent response and its proposed tool use with deterministic
tasks. Treat model output as untrusted text until a tool contract validates it.

1. Use small, targeted prompts from `.pi/skills/roboagent-evaluation/SKILL.md`:
   source explanation, README extraction, repository search, and Git status.
2. Run `tools\pi\test-english-output.ps1` after approval to verify adapter
   output handling. Use `tools\pi\test-roboagent-protocol.ps1` only with an
   approved running host.
3. Record prompt class, latency, requested tool, validation decision, grounded
   evidence path, final-answer language, and QNN context indicator.
4. Reject malformed, unsupported, or mutation-bearing tool requests. Do not
   transform a rejected request into an executable shell command.
5. When the context budget is exhausted, inspect recovery logs and stop; restart
   Pi or the host only after explicit approval.

This skill validates commands and responses; it does not run arbitrary model
suggestions, edit files, or invoke mutation tools by default.
