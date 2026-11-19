"""Embedding backends used by AURA memory."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol

import numpy as np


class EmbeddingBackend(Protocol):
    """Encode text into one vector per input string."""

    dimension: int
    normalized: bool

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        """Return a float32 matrix with shape ``(len(texts), dimension)``."""


class CallableEmbeddingBackend:
    """Adapt a host or device runner to the AURA embedding interface."""

    def __init__(
        self,
        encode: Callable[[Sequence[str]], np.ndarray],
        *,
        dimension: int,
        normalized: bool = True,
    ) -> None:
        self._encode = encode
        self.dimension = dimension
        self.normalized = normalized

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        values = np.asarray(self._encode(texts), dtype=np.float32)
        if values.ndim != 2 or values.shape != (len(texts), self.dimension):
            raise ValueError(
                f"Embedding backend returned {values.shape}; expected "
                f"({len(texts)}, {self.dimension})."
            )
        return values


class SentenceTransformerEmbeddingBackend:
    """Use Sentence Transformers for host-side EmbeddingGemma validation."""

    def __init__(self, model_id: str = "google/embeddinggemma-2") -> None:
        from sentence_transformers import SentenceTransformer

        self.model_id = model_id
        self._model = SentenceTransformer(model_id)
        self.dimension = 768
        self.normalized = True

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        values = self._model.encode(
            list(texts),
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        values = np.asarray(values, dtype=np.float32)
        if values.ndim != 2 or values.shape[1] != self.dimension:
            raise ValueError(
                f"EmbeddingGemma returned {values.shape}; expected "
                f"(batch, {self.dimension})."
            )
        return values
