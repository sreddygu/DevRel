# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""📚 Memory — SQLite (events/metadata) + vector store (Milestone 3).

Persists Events so AURA can answer "What happened while I was away?",
"Where did I leave my laptop?", and "Who came today?". SQLite holds the
structured event log + object locations; a vector store (Chroma/FAISS) holds
embeddings for semantic recall.
"""

from __future__ import annotations

from aura.memory.store import MemoryStore

__all__ = ["MemoryStore"]
