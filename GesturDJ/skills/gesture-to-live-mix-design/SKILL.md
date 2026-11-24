---
name: gesture-to-live-mix-design
description: "Design how a recognized gesture changes music live (clip, tempo, volume, filter, layers) with debounce and a latency budget."
version: 0.1.0
---

# Gesture to Live Mix Design

Back to the [GesturDJ README](../../README.md).

GesturDJ must feel live, but the music model needs minutes per song. So the
design has two paths:

- **Live path (milliseconds):** gesture event -> mix action -> a mixer playing a
  library of clips. This skill designs this path.
- **Background path (minutes, optional):** a sustained or new gesture queues a
  generation request; the new clip joins the library later.

## Steps

1. **Collect** the gesture labels, the clip library manifest and the latency budget
   (default 200 ms from gesture to sound).
2. **Map** each gesture to one mix action: switch clip, change tempo, volume,
   filter, layer on/off. Set `min_confidence`, `debounce_ms` and `cooldown_ms` per
   gesture. A gesture with no action is listed as unmapped.
3. **Budget** the live path: sensor window + inference + mix + audio buffer. If the
   sum exceeds the budget, report which stage to change; do not tune by guess.
4. **Optional background intent:** write a short comma-separated style text, for
   example `acoustic folk, guitar, warm, gentle, female vocal.`, and, if lyrics are
   wanted, an LRC file: one `[mm:ss.xx]` line per timestamp, ascending, **no empty
   lines**, gaps between lines for instrumental passages (a 95 s song fits about
   4 to 12 lines).
5. **Write** `mix_map.json` and the budget table.

## `mix_map.json` shape

```json
{
  "latency_budget_ms": 200,
  "gestures": {
    "swipe_left":  {"action": "previous_clip", "min_confidence": 0.7, "debounce_ms": 300, "cooldown_ms": 500},
    "swipe_right": {"action": "next_clip",     "min_confidence": 0.7, "debounce_ms": 300, "cooldown_ms": 500},
    "circle":      {"action": "toggle_filter", "min_confidence": 0.8, "debounce_ms": 300, "cooldown_ms": 800}
  },
  "unmapped": []
}
```

## Try it

`gesture_scripts/make_test_clips.py` writes stand-in clips, and
`gesture_scripts/live_mixer.py` replays recorded sensor windows through the recognizer and
the mix map, switches the playing clip and times each stage:

```
python gesture_scripts/make_test_clips.py clips
python gesture_scripts/live_mixer.py --model_dir outputs --mix_map mix_map.json --clips clips --events a.csv b.csv --report live-mixer-report.json
```

Measured on a Qualcomm IQ8 (3 gestures, 6 replayed windows, 40 ms audio buffer): 4 applied,
1 debounced, 1 in cooldown; inference 0.5 to 2.3 ms, mix 1 to 5 ms, worst estimated
gesture-to-sound 45.7 ms against the 200 ms budget
([`mix_map.json`](../../evidence/iq8-run/mix_map.json),
[`live-mixer-report.json`](../../evidence/iq8-run/live-mixer-report.json)). The estimate ends at
"player started plus configured buffer"; it was not measured at the speaker and no real
gesture was used. It understates the audio stage: at the driver level a cold player start reaches the hardware
236 to 280 ms after the gesture is handled, over the whole budget (see
[`audio-output-integration`](../audio-output-integration/SKILL.md)).

Complete only when every label is mapped or listed unmapped and the budget adds
up. Whether it feels live is confirmed later, with a real gesture, by a
separate validation step (a human-in-the-loop gate; see finding F8).
