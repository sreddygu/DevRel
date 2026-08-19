# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""🧠🤖 Agent — local LLM reasoning + actuator tools (Milestones 4 & 5).

Milestone 4 ("Brain") adds a local LLM (Gemma/Qwen via an on-device
llama.cpp / Genie server) to summarize and reason over remembered Events.
Milestone 5 ("Action") gives the agent tools to act on the world — lights,
relays, smart devices, a mobile robot — orchestrated with LangGraph.
"""

from __future__ import annotations

from aura.agent.llm import LocalLLM
from aura.agent.tools import Tool, default_tools

__all__ = ["LocalLLM", "Tool", "default_tools"]
