"""Wearable AI proxy: sensor fusion, context classification and gated burst-to-hub."""

from .context import classify
from .node import WearableNode
from .sensors import DEFAULT_SCENARIO, simulate

__all__ = ["DEFAULT_SCENARIO", "WearableNode", "classify", "simulate"]
