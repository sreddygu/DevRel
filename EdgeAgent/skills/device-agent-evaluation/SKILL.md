# EdgeAgent Device Agent Evaluation

Produce an evidence-backed EdgeAgent evaluation for a user-approved target
without silently transferring models, converting artifacts, or changing the
device.

1. Run `devrel-agent detect --local-only --json` to capture host capabilities.
2. For a remote target, run `devrel-agent profile-device` with a model path or
   approved server artifact reference supplied at runtime.
3. Use `--convert` only after explicit approval; conversion may invoke remote
   services and produce a new artifact.
4. Run the focused local coverage before device work:
   `python -m pytest tests/test_local/test_device_agent.py tests/test_local/test_profile_device_cli.py -q`.
5. Capture the target class, transport, model identifier, provider or backend,
   latency/throughput result, command exit status, and known limitations in a
   dated report. Mark unobserved data as `unknown`.

Model upload, SSH/ADB execution, remote conversion, and board test-suite
execution require explicit approval. Never flash, reboot, alter networking, or
store target credentials as part of this skill.
