"""Fraud-safety question search: "should I tell my OTP to the bank?" -> an answer.

A search engine over a fixed, reviewed knowledge base (fixtures/knowledge.json),
not a text generator. In a money-safety app a fluent wrong answer is the worst
possible output, and the people this is for cannot check one. So every answer
the user can receive was written and reviewed in advance, in all four
languages, and the search's only job is to find the right one -- or to admit
that none fits.

Same retrieval as scheme search (multilingual-e5 over each entry's question and
answer in all four languages, plus keyword hits), with one addition: a
**no-answer threshold**. e5 gives every pair of sentences a similarity, so an
off-topic question ("cricket score?") would otherwise always return its least
bad match. Below the threshold the API says it has no good answer and points to
1930 instead. The threshold is measured, not guessed: ml/eval_fraud_qa.py.
"""
from __future__ import annotations

import json
import re
import threading
from functools import lru_cache
from pathlib import Path

import numpy as np

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "knowledge.json"
LANGUAGES = ("hi", "en", "ta", "te")

# Per keyword hit, added to the cosine. Same scale reasoning as scheme search.
KEYWORD_WEIGHT = 0.01
# Best score below which the search answers "no good answer". From
# ml/eval_fraud_qa.py: the lowest threshold at which none of the 8 off-topic
# questions is answered, keeping 85% of 40 in-domain questions answered right.
# The margin is thin -- highest off-topic 0.820, lowest in-domain 0.828 -- so
# re-run the eval whenever entries are added.
MIN_SCORE = 0.825

_lock = threading.Lock()
_index: dict | None = None


class KnowledgeError(ValueError):
    pass


@lru_cache(maxsize=1)
def load_entries() -> tuple[dict, ...]:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    seen = set()
    for e in raw["entries"]:
        if e["id"] in seen:
            raise KnowledgeError(f"duplicate id {e['id']}")
        seen.add(e["id"])
        for key in ("q", "a"):
            missing = [l for l in LANGUAGES if not e.get(key, {}).get(l)]
            if missing:
                raise KnowledgeError(f"{e['id']}: {key} missing {missing}")
        for link in e.get("links", []):
            if not link["href"].startswith(("tel:", "https://")):
                raise KnowledgeError(f"{e['id']}: link must be tel: or https://")
    return tuple(raw["entries"])


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _keyword_hits(entry: dict, query: str) -> int:
    q = _norm(query)
    return sum(1 for kw in entry.get("keywords", []) if _norm(kw) in q)


def _build(embedder) -> dict:
    entries = load_entries()
    texts, owner = [], []
    for i, e in enumerate(entries):
        for lang in LANGUAGES:
            # The question carries most of the signal; the answer adds the
            # vocabulary people use when they describe what happened to them.
            texts.append(f"{e['q'][lang]} {e['a'][lang]}")
            owner.append(i)
    return {"vectors": embedder.encode_passages(texts), "owner": np.array(owner)}


def score_all(query: str, embedder=None, mode: str = "hybrid") -> list[tuple[dict, float]]:
    """Every entry with its score, best first. mode: hybrid | embedding | keyword."""
    global _index
    entries = load_entries()
    kw = np.array([_keyword_hits(e, query) for e in entries], dtype=float)
    if mode == "keyword" or embedder is None or not embedder.available:
        scores = kw
    else:
        with _lock:
            if _index is None:
                _index = _build(embedder)
        q = embedder.encode_queries([query])[0]
        sims = _index["vectors"] @ q
        best = np.full(len(entries), -1.0)
        np.maximum.at(best, _index["owner"], sims)
        scores = best if mode == "embedding" else best + KEYWORD_WEIGHT * kw
    return sorted(zip(entries, scores.tolist()), key=lambda p: -p[1])


def localise(entry: dict, lang: str) -> dict:
    return {"id": entry["id"], "topic": entry.get("topic", ""), "icon": entry.get("icon", "shield"),
            "question": entry["q"][lang], "answer": entry["a"][lang],
            "links": entry.get("links", [])}


def ask(query: str, embedder, lang: str, k: int = 4) -> dict:
    """Best answer plus related questions, or an honest no-answer."""
    ranked = score_all(query, embedder)
    semantic = embedder is not None and embedder.available
    if semantic:
        confident = bool(ranked) and ranked[0][1] >= MIN_SCORE
    else:
        # Keyword-only mode: one hit is the weakest evidence that counts.
        confident = bool(ranked) and ranked[0][1] >= 1
    results = [{**localise(e, lang), "score": round(s, 4)} for e, s in ranked[:k]]
    return {
        "query": query,
        "language": lang,
        "backend": "embedding+keyword" if semantic else "keyword",
        "answered": confident,
        "best": results[0] if confident else None,
        # When unsure, the near misses are still offered -- as "maybe you meant",
        # never as the answer.
        "related": results[1:] if confident else results[:3],
    }


def featured(lang: str) -> list[dict]:
    return [{"id": e["id"], "question": e["q"][lang]} for e in load_entries() if e.get("featured")]
