# Author: Srinivas Reddy Gudala
# Email: sreddygu@qti.qualcomm.com
# Last Updated: 2026-08-17
# Version: 1.0
#
"""Actuator / IoT tools for the agent (Milestone 5, "Action").

Tools the LLM agent can call to act on the physical world — lights, relays,
smart devices, a mobile robot.

Each :class:`Tool` produces an ``action`` :class:`~aura.core.events.Event` when
run, so actions are remembered alongside perceptions. Smart-home capabilities
use an injectable :class:`SmartHomeTransport` so tests run hardware-free and
real adapters (MQTT, Home Assistant, serial relay) can be swapped in.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from aura.core.events import Event


@dataclass
class Tool:
    """A callable capability the agent can invoke.

    Attributes:
        name: Stable tool id, e.g. ``"set_light"``.
        description: One line the LLM sees when choosing tools.
        run: The implementation ``(**kwargs) -> str | Event``.
        parameters: JSON-Schema-style parameter spec forwarded to the LLM when
            building the tool list for ``/v1/chat/completions``.
    """

    name: str
    description: str
    run: Callable[..., str | Event]
    parameters: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})

    def invoke(self, **kwargs: object) -> Event:
        """Run the tool and wrap the outcome as an ``action`` Event."""
        result = self.run(**kwargs)
        if isinstance(result, Event):
            return result
        return Event(
            event=f"{self.name}: {result}",
            type="action",
            source="agent",
            attributes={"tool": self.name, "args": kwargs},
        )

    def to_openai_spec(self) -> dict[str, Any]:
        """Return the OpenAI tool-calling spec dict for this tool."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# ── Smart-home transport seam ─────────────────────────────────────────────────

class SmartHomeTransport(Protocol):
    """Minimal protocol for light/relay/scene adapters."""

    def set_light(self, name: str, state: str) -> str: ...

    def run_scene(self, name: str) -> str: ...


class MockSmartHomeTransport:
    """Hardware-free transport that records calls and returns canned responses."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    def set_light(self, name: str, state: str) -> str:
        self.calls.append(("set_light", {"name": name, "state": state}))
        return f"{name} turned {state}"

    def run_scene(self, name: str) -> str:
        self.calls.append(("run_scene", {"name": name}))
        return f"scene '{name}' activated"


# ── Tool factories ────────────────────────────────────────────────────────────

def smart_home_tools(transport: SmartHomeTransport) -> list[Tool]:
    """Return set_light and run_scene tools backed by *transport*."""
    return [
        Tool(
            "set_light",
            "Turn a named light or relay on or off.",
            lambda **kw: transport.set_light(kw["name"], kw["state"]),
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Light or relay name, e.g. 'workshop'"},
                    "state": {"type": "string", "enum": ["on", "off"]},
                },
                "required": ["name", "state"],
            },
        ),
        Tool(
            "run_scene",
            "Activate a named smart-home scene.",
            lambda **kw: transport.run_scene(kw["name"]),
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Scene name, e.g. 'movie night'"},
                },
                "required": ["name"],
            },
        ),
    ]


def _not_implemented(milestone: str) -> Callable[..., str]:
    def _run(**_: object) -> str:
        raise NotImplementedError(f"{milestone} — see docs/ROADMAP.md")

    return _run


def default_tools(
    *,
    robot: object | None = None,
    smart_home: SmartHomeTransport | None = None,
) -> list[Tool]:
    """Return the default tools with optional hardware backends.

    Without backends the smart-home tools raise ``NotImplementedError`` (stub
    mode). Pass a :class:`SmartHomeTransport` (or :class:`MockSmartHomeTransport`
    for tests) to get live behaviour. Pass a :class:`~aura.agent.robot.SafeRobotController`
    for robot tools.
    """
    if smart_home is not None:
        tools = smart_home_tools(smart_home)
    else:
        milestone = "Milestone 5 (Action)"
        tools = [
            Tool("set_light", "Turn a light or relay on/off (args: name, state).", _not_implemented(milestone)),
            Tool("run_scene", "Activate a smart-home scene by name.", _not_implemented(milestone)),
        ]
    if robot is not None:
        from aura.agent.robot import robot_tools

        tools.extend(robot_tools(robot))
    return tools
