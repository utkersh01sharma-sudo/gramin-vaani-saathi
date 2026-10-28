"""Sentence embeddings for search, behind the same lazy-singleton pattern as the
other adapters.

multilingual-e5 expects a role prefix -- "query: " for what the user said and
"passage: " for what is being searched. Leaving it off costs several points of
retrieval accuracy for no visible error, which is why the prefixes are applied
here once instead of being remembered at every call site.

If the model cannot be loaded (no torch, no network on first run, artifact
missing) ``available`` is False and callers use keyword matching instead. Search
degrades; it never breaks.
"""
from __future__ import annotations

import logging
import threading

import numpy as np
from django.conf import settings

logger = logging.getLogger(__name__)


class Embedder:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or getattr(settings, "EMBEDDING_MODEL", "")
        self._model = None
        self._failed = False
        self._lock = threading.Lock()

    def _load(self):
        if self._model is not None or self._failed or not self.model_name:
            return self._model
        with self._lock:
            if self._model is None and not self._failed:
                try:
                    from sentence_transformers import SentenceTransformer

                    # CPU on purpose: a 118M encoder embeds one query in ~15 ms
                    # on CPU, and the GPU is better left to the classifiers.
                    self._model = SentenceTransformer(self.model_name, device="cpu")
                    logger.info("embedder loaded: %s", self.model_name)
                except Exception:  # noqa: BLE001 -- any failure means "use keywords"
                    logger.exception("embedder unavailable; search falls back to keywords")
                    self._failed = True
        return self._model

    @property
    def available(self) -> bool:
        return self._load() is not None

    def encode_queries(self, texts: list[str]) -> np.ndarray:
        return self._encode([f"query: {t}" for t in texts])

    def encode_passages(self, texts: list[str]) -> np.ndarray:
        return self._encode([f"passage: {t}" for t in texts])

    def _encode(self, texts: list[str]) -> np.ndarray:
        model = self._load()
        if model is None:
            raise RuntimeError("embedder not available")
        return model.encode(
            texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
        )
