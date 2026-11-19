# Audio Output Integration

Back to the [GesturDJ README](../../README.md).

The audio stage can use more of the 200 ms budget than everything else together, and
it is the stage people guess. This skill measures it on the board that will play.

## Probe

```
python gesture_scripts/probe_audio_output.py --runs 5 --out audio-output-probe.json
```

It lists the sound card (`aplay -l`) and the players on PATH, then plays a silent
100 ms clip through each player at its default buffer and at a 40 ms buffer. Overhead
is the wall time minus the 100 ms clip: player start-up plus the buffer drain.

## Measured (Qualcomm IQ8, 5 runs each)

| Player and buffer | Median overhead | Max |
| --- | --- | --- |
| `aplay`, default | 159 ms | 237 ms |
| `aplay`, 40 ms | **112 ms** | 134 ms |
| `paplay`, default | 173 ms | 178 ms |
| `paplay`, 40 ms | 152 ms | 160 ms |
| `pw-play`, default | 130 ms | 146 ms |
| `pw-play`, 40 ms | 133 ms | 135 ms |

All exited 0 ([`audio-output-probe.json`](../../evidence/iq8-run/audio-output-probe.json)).

## Driver-level check (closer to sound)

The table above times the player process. That is not when sound starts: a player can exit before
the hardware has played anything. So the second probe watches the audio hardware itself:

```
python3 gesture_scripts/probe_hw_latency.py --runs 6 --out hw-latency.json     # on the board
```

It starts each player on a cold device and polls `/proc/asound/cardN/pcmNp/sub0/status` every 2 ms until
the state is `RUNNING` (the hardware is consuming samples), then adds the frames already queued ahead of the
converter (`delay`, 2528 frames at 48 kHz = 52.7 ms).

| Player, cold device | Time to RUNNING | Queue | First sound (median) | Max |
| --- | --- | --- | --- | --- |
| `pw-play` | 183.5 ms | 52.7 ms | **236 ms** | 249 ms |
| `aplay` (default device) | 184.2 ms | 52.7 ms | 237 ms | 241 ms |
| `paplay` | 226.9 ms | 52.7 ms | 280 ms | 288 ms |
| warm device (already RUNNING) | 0 | 52.7 ms | at least 53 ms | |

Every cold start is over the 200 ms budget on its own ([`hw-latency.json`](../../evidence/iq8-run/hw-latency.json)).
The warm figure is a floor from the queue alone, not a measurement of a warm stream.

**Correction:** the process-level overhead above (112 to 237 ms) is not an upper bound for first sound. The
player exits when its own clock says the clip is done, not when the hardware has played it, so it understates
a cold start by about 100 ms or more. Use the driver-level number.

**Fix, built and measured:** do not start a player per gesture. [`warm_output.py`](../../gesture_scripts/warm_output.py)
starts one `pw-cat` stream when the mixer starts, keeps it open, sends 10 ms chunks in real time and swaps in a
clip's samples on a gesture (`live_mixer.py --player warm`). Two details matter: the pipe to `pw-cat` is capped at
4096 bytes, because audio written before the stream connects otherwise queues in the pipe and shows up as a constant
extra latency (164 ms in two runs here); and the stream runs at 48 kHz, the sound server's rate, because 16 kHz
adds a resampler and wider jitter.

```
python3 gesture_scripts/probe_warm_stream.py --trials 12 --hw_queue_ms 52.7 --out warm-stream.json
```

It writes a click into a temporary null sink and times its arrival with a recorder on the sink's monitor:

| Path to the sink (3 runs of 12) | p50 | p95 | Max |
| --- | --- | --- | --- |
| Warm stream | 37 to 38 ms | 44 to 48 ms | 59 ms |
| Player started per gesture (sound server already running) | 116 to 132 ms | 145 to 152 ms | 153 ms |

Add the hardware queue (52.7 ms measured; 23 to 31 ms when the warm stream is the only client,
[`warm-hw-status.txt`](../../evidence/iq8-run/warm-hw-status.txt)) for the path to the converter: the warm stream
is about 100 ms at its worst, against 236 to 280 ms for a cold player start. The null sink is a proxy: the real
sink runs its own graph cycle, and the recorder reads 10 ms chunks. Evidence:
[`warm-stream.json`](../../evidence/iq8-run/warm-stream.json).

## Speaker level

Checked and not possible on this board as it stands: the sound server lists a speaker and a microphone, but
a 1 kHz tone played through the speaker was not heard by the microphone (microphone level 7 with the tone
against 25 without), so no speaker or microphone is attached. A true speaker-level check needs a speaker and a
microphone (or a recorder on the line out) and a click played at a known time.

## Rules

- Name a best setting only from runs that exited 0.
- Use the driver-level first-sound figure as the audio stage. The process-level overhead is not an upper bound.
- Neither probe is acoustic. A player exiting 0 does not prove a speaker is attached: ask the developer to listen.
- Pass the audio stage to `live-mixer-and-latency-validation`.

Complete when `audio-output-probe.json`, `hw-latency.json` and `warm-stream.json` exist and name a best setting, or name the failed player.
