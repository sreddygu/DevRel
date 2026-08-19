# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""Core: the Event contract and the orchestration pipeline.

`aura.core` holds the pieces every other module depends on:

* :mod:`aura.core.events`   — the :class:`Event` dataclass, the single data
  contract that vision/speech produce and memory/agent consume.
* :mod:`aura.core.pipeline` — :class:`AuraPipeline`, the perceive → remember →
  reason → act loop that wires the modules together.
"""

from __future__ import annotations

from aura.core.events import Event

__all__ = ["Event"]
