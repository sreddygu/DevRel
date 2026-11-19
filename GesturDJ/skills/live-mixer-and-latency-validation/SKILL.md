# Live Mixer and Latency Validation

Back to the [GesturDJ README](../../README.md).

Checks that the live path (gesture window, recognizer, mix action, audio player) fits the
budget, many times over, not once.

```
python gesture_scripts/live_mixer.py --model_dir outputs --mix_map mix_map.json --clips clips --events a.csv b.csv --report live-mixer-report.json
python gesture_scripts/validate_live_latency.py --model_dir outputs --clips clips --windows DATA --runs 200 --buffer_ms 134 --out live-latency.json
```

The first replays a few gestures and shows what the mix map does (applied, debounced, cooldown,
below confidence). The second replays hundreds with debounce off and reports p50, p95 and max per
stage. Its `--buffer_ms` is the audio stage: use the measured overhead from
[`audio-output-integration`](../audio-output-integration/SKILL.md).

## Measured (Qualcomm IQ8, 200 replayed gestures, synthetic windows)

| Audio stage assumed | Total p95 | Verdict |
| --- | --- | --- |
| 40 ms (the configured buffer only) | 52.8 ms | pass, but understates the audio stage |
| 500 ms (a large default buffer) | 511 ms | **fail** |
| 134 ms (process-level player overhead) | 145.3 ms | pass, but this overhead was not a real upper bound |
| 249 ms (driver-level cold start of the best player, worst case) | 260.6 ms | **fail** (a player per gesture) |
| 112 ms (warm output stream, worst case plus the 52.7 ms hardware queue) | **112.6 ms** | **pass** (`--player warm`) |

Recognizer p95 is 2.4 ms and the mix step p95 is 11 ms, so the audio stage decides the result. The driver-level row uses the cold-start figures from [`audio-output-integration`](../audio-output-integration/SKILL.md), so spawning a player per gesture fails the budget on this board. One output stream kept open ([`warm_output.py`](../../gesture_scripts/warm_output.py), `--player warm`) passes: with the worst warm figure (59 ms to the sink, from [`audio-output-integration`](../audio-output-integration/SKILL.md)) plus the 52.7 ms hardware queue, the live path's p95 is 112.6 ms, and the recognizer plus mix step now cost under 1 ms because no process is started
([`buffer40`](../../evidence/iq8-run/live-latency-buffer40.json),
[`buffer500`](../../evidence/iq8-run/live-latency-buffer500.json),
[`measured overhead`](../../evidence/iq8-run/live-latency-measured-overhead.json),
[`driver level`](../../evidence/iq8-run/live-latency-driver-level.json),
[`warm stream`](../../evidence/iq8-run/live-latency-warm.json), [`warm replay`](../../evidence/iq8-run/live-mixer-warm.json),
[`replay`](../../evidence/iq8-run/live-mixer-report.json)).

## Rules

- Use the driver-level audio stage for the verdict, not the configured buffer or the process-level overhead.
- A failed check is reported with the stage that dominates. Never raise the budget or lower the audio figure to pass.
- Replay is not feel. A person with a real gesture and a speaker confirms it is live (finding F8).

Complete when `live-latency.json` exists with a verdict that names the dominant stage.
