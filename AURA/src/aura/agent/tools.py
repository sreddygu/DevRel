# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""Actuator / IoT tools for the agent (Milestone 5, "Action").

Tools the LLM agent can call to act on the physical world — lights, relays,
smart devices, a mobile robot. At v0.1 these are declarations + stubs; the
LangGraph agent loop that selects and invokes them is wired in Milestone 5.

Each :class:`Tool` produces an ``action`` :class:`~aura.core.events.Event` when
run, so actions are remembered alongside perceptions.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from aura.core.events import Event


@dataclass
class Tool:
    """A callable capability the agent can invoke.

    Attributes:
        name: Stable tool id, e.g. ``"set_light"``.
        description: One line the LLM sees when choosing tools.
        run: The implementation ``(**kwargs) -> str``. Stub tools raise
            ``NotImplementedError``.
    """

    name: str
    description: str
    run: Callable[..., str]

    def invoke(self, **kwargs: object) -> Event:
        """Run the tool and wrap the outcome as an ``action`` Event."""
        result = self.run(**kwargs)
        return Event(
            event=f"{self.name}: {result}",
            type="action",
            source="agent",
            attributes={"tool": self.name, "args": kwargs},
        )


def _not_implemented(milestone: str) -> Callable[..., str]:
    def _run(**_: object) -> str:
        raise NotImplementedError(f"{milestone} — see docs/ROADMAP.md")

    return _run


def default_tools() -> list[Tool]:
    """The starter tool set (all stubs until Milestone 5)."""
    m5 = "Milestone 5 (Action)"
    return [
        Tool("set_light", "Turn a light or relay on/off (args: name, state).", _not_implemented(m5)),
        Tool("run_scene", "Activate a smart-home scene by name.", _not_implemented(m5)),
        Tool("move_robot", "Command the mobile robot (args: direction, distance).", _not_implemented(m5)),
    ]
