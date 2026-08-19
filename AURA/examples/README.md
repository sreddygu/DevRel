# AURA Examples

Runnable, self-contained demos land here as each milestone is implemented
(see `../docs/ROADMAP.md`). Each example gets its own short docstring and only
uses the optional-dependency group for its milestone.

Planned:

| Example            | Shows                                             | Needs milestone |
|--------------------|---------------------------------------------------|-----------------|
| `eyes_demo.py`     | camera → YOLO → Event JSON printed to stdout      | 1 (Eyes)        |
| `listen_demo.py`   | mic → Whisper transcript → Event                  | 2 (Ears)        |
| `memory_demo.py` ✅ | add Events → query / `where_is` / semantic recall | 3 (Memory)      |
| `ask_demo.py` ✅    | "What happened today?" → local LLM summary        | 4 (Brain)       |

`memory_demo.py` runs on the base install. `ask_demo.py` needs the `agent`
extra (`pip install -e ".[agent]"`) and a local LLM server at
`AURA_LLM_BASE_URL`; without one it prints the retrieved context instead.

Until then, the smoke test doubles as the smallest working example:

```bash
pip install -e ".[dev]"
pytest -q
```
