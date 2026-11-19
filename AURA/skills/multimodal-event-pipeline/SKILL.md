# AURA Multimodal Event Pipeline

Validate the AURA perception-to-memory event pipeline with test fixtures or
approved synthetic input before using live sensors.

1. Start from a completed AURA runtime setup and identify the selected stages:
   vision, speech, memory, or grounded reasoning.
2. Run focused tests from `AURA`: `pytest -q tests/test_vision.py
   tests/test_speech.py tests/test_memory.py tests/test_smoke.py`.
3. Inspect the resulting event fields and preserve only redacted, synthetic, or
   approved evidence. Record source type, event count, stage outcomes, and
   unknown fields.
4. For live camera or microphone capture, get explicit approval before opening
   the sensor and confirm the permitted retention location and duration.
5. Do not claim end-to-end on-device validation unless all selected stages were
   observed on the named target.

This skill does not enable sensors, upload event data, or change model/runtime
configuration by default.
