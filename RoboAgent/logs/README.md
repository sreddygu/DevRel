# RoboAgent Logs

This folder contains generated runtime and validation output. It is excluded from
RoboAgent workspace search results.

- `host.stdout.log` and `host.stderr.log` — current QNN host output.
- `host-recovery-*.log` — host restart and readiness diagnostics.
- `pi-protocol.jsonl` — optional adapter request/response trace when
  `ROBOAGENT_DEBUG_PROTOCOL=1`.
- `evaluation-results.jsonl` — structured evaluation results.
- `tests/` — isolated mock-protocol and English-output test logs.
- `archive/` — historical test and benchmark output moved from earlier runs.

`.roboagent-runtime/` is intentionally separate. It contains short-lived
control files such as host-ready markers and the disposable mutation fixture,
not logs.
