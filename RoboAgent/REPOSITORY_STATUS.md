# Repository Status

This folder is an exported/runtime artifact rather than a Git source checkout.
It contains prebuilt QNN runners, the compiled Gemma model, runtime logs, and a
small Pi integration layer. There is no `.git` directory here, so Git status and
history are unavailable until this directory is placed inside a source checkout
or initialized as one.

The Pi integration validates tool calls, records structured evaluation signals in
`logs/evaluation-results.jsonl`, reports per-request token and QNN
context usage, enforces English-only output, and can restart/replay the host
after the estimated context budget is exhausted when launched through
`tools/pi/start-roboagent-pi.ps1`.
