from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_e2e_module():
    path = Path(__file__).parents[1] / "deploy" / "iq8" / "aura_e2e.py"
    spec = importlib.util.spec_from_file_location("aura_deploy_e2e", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_light_action_turns_off_without_people() -> None:
    action, result = _load_e2e_module().light_action(0)
    assert action == "set_light(porch, OFF)"
    assert result == "porch light OFF — no person detected"


def test_light_action_turns_on_with_people() -> None:
    action, result = _load_e2e_module().light_action(3)
    assert action == "set_light(porch, ON)"
    assert result == "porch light ON — 3 person(s) detected"
