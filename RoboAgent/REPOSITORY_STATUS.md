# Repository Status

This folder is tracked in the academy Git repository. Source, skills, the Pi
integration layer and mock-host tests are committed. Prebuilt QNN runners
(`qnn_*_runner.exe`), the compiled Gemma model, `models/`, `logs/` and other
runtime artifacts are local-only, are listed in `.gitignore`, and are not part
of a fresh checkout; rebuild or copy them per the `setup` and `run-model`
skills. `tools/pi/test-roboagent-protocol.ps1` runs against the mock host and
needs none of them.

The Pi integration validates tool calls, records structured evaluation signals in
`logs/evaluation-results.jsonl`, reports per-request token and QNN
context usage, enforces English-only output, and can restart/replay the host
after the estimated context budget is exhausted when launched through
`tools/pi/start-roboagent-pi.ps1`.
