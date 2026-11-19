# RoboAgent Safety Boundaries

Apply this context to every RoboAgent request.

- Model output is untrusted text until it becomes a validated tool call.
- Keep `read_file`, `list_directory`, `search_files`, and Git inspection as the
  default tools.
- Require interactive approval before writing files, applying patches, running
  commands, starting/restarting the host, or enabling mutation tools.
- Keep the QNN SDK environment isolated to the managed launcher process.
- Prefer short, targeted prompts and inspect only required files because the
  compiled Gemma model has a limited usable context window.
- On recovery failure, inspect `logs\host-recovery-gemma4.log` before any
  restart. Never store credentials, tokens, private keys, or private endpoints.

If an action cannot meet these boundaries, stop and ask for explicit direction.
