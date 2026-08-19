# CLAUDE.md — AURA

Context for Claude Code working in this repo. AURA = **Autonomous Understanding
& Responsive Agent**: a privacy-first Physical-AI agent that runs entirely
on-device on the **Arduino VENTUNO Q** (see, hear, remember, reason, act — no
cloud). This is a normal Python code repo; the surrounding Obsidian-vault
conventions do **not** apply here.

## Layout

- `src/aura/` — the `aura` package (installable, `src/` layout).
  - `core/` — `events.py` (the `Event` data contract, the one seam everything
    shares) and `pipeline.py` (`AuraPipeline`, the perceive→remember→reason→act
    loop). **`events.py` is the only fully-implemented module.**
  - `vision/` (Milestone 1), `speech/` (2), `memory/` (3), `agent/` (4/5),
    `dashboard/` — milestone modules, currently **importable stubs**.
  - `config.py` (`AURA_*` env/`.env` settings), `cli.py` (`aura` entry point).
- `docs/ARCHITECTURE.md` (diagram + Event schema), `docs/ROADMAP.md` (Milestones 1–5).
- `tests/test_smoke.py`, `examples/`, `scripts/`.

## Key conventions

- **Python 3.10+.** Package uses `from __future__ import annotations`.
- **Light base install.** Base deps are only `numpy` + `pydantic`. Everything
  heavy (`opencv`, `onnxruntime`, `whisper`, `chromadb`, `httpx`, `langgraph`,
  `fastapi`) lives in optional-dependency groups in `pyproject.toml`
  (`vision`, `speech`, `memory`, `agent`, `dashboard`, `dev`).
- **Lazy heavy imports.** Import `cv2`/`onnxruntime`/`whisper`/`fastapi`/etc.
  *inside* the method that uses them, never at module top level — so
  `import aura` and the smoke test pass with only the base install. Preserve
  this when implementing milestones.
- **Stubs** raise `NotImplementedError("Milestone N (Name) — see docs/ROADMAP.md")`.
- **One contract:** vision/speech produce `Event`s; memory stores them; the
  agent reasons over them. Don't add parallel data types — extend `Event`.
- **Local-first / privacy-first.** No cloud calls. The LLM is an on-device
  OpenAI-compatible server (llama.cpp / Genie) reached via `127.0.0.1`.
- **Secrets:** never commit `.env` (only `.env.example`, blank). No board
  passwords in the repo — use SSH keys or a password manager.

## Quick commands

```bash
pip install -e ".[dev]"          # base + test/lint tooling
pytest -q                        # smoke tests (imports + Event round-trip)
ruff check src tests             # lint
aura config                      # print resolved AURA_* settings
aura --version
```

## Resume protocol

1. `pytest -q` — confirms the scaffold is intact (all modules import, Event
   round-trips). Start here.
2. Read `docs/ROADMAP.md` for the current milestone and its definition-of-done.
3. When implementing a milestone: install its extra
   (`pip install -e ".[vision]"`), replace the stubs, keep heavy imports lazy,
   add a runnable `examples/<name>_demo.py`, and extend `tests/`.

## Target hardware

Arduino VENTUNO Q — dual-brain (AI-inference SoC + real-time MCU) running Ubuntu
Linux on the AI side. Perception + reasoning run on the Linux side; Milestone 5
actuation is delivered through the real-time MCU side.
