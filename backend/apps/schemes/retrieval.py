"""Find schemes from what someone says, in any of the four languages.

"मुझे खेती के लिए पैसा चाहिए" has to reach PM-KISAN and KCC even though neither
name appears in it. Two signals, combined:

* **Embeddings** (multilingual-e5-small). Each scheme is indexed as four
  passages, one per language, and scores the best of the four -- so a Tamil
  query is matched against the Tamil description, not a translation of it.
* **Keywords** from the fixture. Cheap, exact, and the only signal when the
  encoder is unavailable.

The blend weight and the comparison against each signal alone are measured,
not assumed: see ml/eval_scheme_search.py and ml/reports/scheme_search.json.
"""
from __future__ import annotations

import re
import threading

import numpy as np

from .catalog import load_schemes
from .engine import LANGUAGES, Scheme

# Added to the cosine score per keyword hit. e5 cosines for related and
# unrelated passages sit within a few hundredths of each other, so a keyword hit
# is worth a lot relative to that spread. 0.01 is the sweep winner in
# ml/eval_scheme_search.py: hit@1 0.875 vs 0.812 embedding-only, 0.604 keyword-only.
KEYWORD_WEIGHT = 0.01

_index_lock = threading.Lock()
_index: dict | None = None


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def passages(scheme: Scheme) -> list[str]:
    return [
        f"{scheme.name[lang]}. {scheme.summary[lang]} {scheme.benefit[lang]}"
        for lang in LANGUAGES
    ]


def keyword_hits(scheme: Scheme, query: str) -> int:
    q = _normalise(query)
    names = [_normalise(scheme.name[lang]) for lang in LANGUAGES]
    hits = sum(1 for kw in scheme.keywords if _normalise(kw) in q)
    # Saying the scheme's own name is the strongest signal there is.
    hits += 3 * sum(1 for name in names if name and name in q)
    return hits


def _build_index(embedder) -> dict:
    schemes = load_schemes()
    texts, owner = [], []
    for i, scheme in enumerate(schemes):
        for passage in passages(scheme):
            texts.append(passage)
            owner.append(i)
    return {
        "schemes": schemes,
        "vectors": embedder.encode_passages(texts),
        "owner": np.array(owner),
    }


def _embedding_scores(query: str, embedder) -> np.ndarray | None:
    global _index
    if embedder is None or not embedder.available:
        return None
    with _index_lock:
        if _index is None:
            _index = _build_index(embedder)
    q = embedder.encode_queries([query])[0]
    sims = _index["vectors"] @ q
    n = len(_index["schemes"])
    best = np.full(n, -1.0)
    np.maximum.at(best, _index["owner"], sims)
    return best


def score_all(query: str, embedder=None, mode: str = "hybrid") -> list[tuple[Scheme, float]]:
    """Score every scheme. ``mode`` is hybrid | embedding | keyword (for the eval)."""
    schemes = load_schemes()
    kw = np.array([keyword_hits(s, query) for s in schemes], dtype=float)
    emb = _embedding_scores(query, embedder) if mode != "keyword" else None

    if mode == "embedding" and emb is not None:
        scores = emb
    elif emb is not None:
        scores = emb + KEYWORD_WEIGHT * kw
    else:
        scores = kw
    return sorted(zip(schemes, scores.tolist()), key=lambda p: -p[1])


def search(query: str, embedder=None, k: int = 3) -> tuple[list[tuple[Scheme, float]], str]:
    """Top-k schemes and which signal produced them ("embedding+keyword" or "keyword")."""
    ranked = score_all(query, embedder)
    backend = "embedding+keyword" if (embedder is not None and embedder.available) else "keyword"
    if backend == "keyword":
        # Without embeddings a zero score means "no keyword matched" -- returning
        # arbitrary schemes in fixture order would look like an answer and is not.
        ranked = [pair for pair in ranked if pair[1] > 0]
    return ranked[:k], backend
