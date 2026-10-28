"""Measure scheme search: keyword vs embedding vs hybrid, and pick the blend weight.

48 hand-written queries (12 per language) that describe a need without naming
the scheme -- "my crops were destroyed by the flood", not "PMFBY". Each lists
every scheme that would be a correct answer, so "pension" may be satisfied by
APY or NSAP. Hit@1 is what a voice reply speaks first; hit@3 is what the screen
shows.

    python ml/eval_scheme_search.py

Writes ml/reports/scheme_search.json.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django  # noqa: E402

django.setup()

from ai.local.embedder import Embedder  # noqa: E402
from apps.schemes import retrieval  # noqa: E402

QUERIES = ROOT / "ml" / "data" / "scheme_queries.jsonl"
OUT = ROOT / "ml" / "reports" / "scheme_search.json"
WEIGHTS = (0.005, 0.01, 0.02, 0.03, 0.05, 0.08)


def evaluate(rows, embedder, mode):
    hit1 = hit3 = 0
    per_lang: dict[str, list[int]] = {}
    misses = []
    for row in rows:
        ranked = [s.id for s, _ in retrieval.score_all(row["text"], embedder, mode=mode)]
        h1 = ranked[0] in row["relevant"]
        h3 = any(r in row["relevant"] for r in ranked[:3])
        hit1 += h1
        hit3 += h3
        per_lang.setdefault(row["lang"], []).append(int(h1))
        if not h1:
            misses.append({"text": row["text"], "expected": row["relevant"], "got": ranked[:3]})
    n = len(rows)
    return {
        "hit_at_1": round(hit1 / n, 4),
        "hit_at_3": round(hit3 / n, 4),
        "per_language_hit_at_1": {k: round(sum(v) / len(v), 4) for k, v in per_lang.items()},
        "misses": misses,
    }


def main():
    rows = [json.loads(line) for line in QUERIES.read_text(encoding="utf-8").splitlines() if line.strip()]
    embedder = Embedder()
    results = {
        "keyword": evaluate(rows, embedder, "keyword"),
        "embedding": evaluate(rows, embedder, "embedding"),
    }
    sweep = {}
    for w in WEIGHTS:
        retrieval.KEYWORD_WEIGHT = w
        sweep[w] = evaluate(rows, embedder, "hybrid")
    # Ties go to the smaller weight: the less the keywords are trusted, the
    # less a stray substring match can override what the sentence means.
    best_w = max(sweep, key=lambda w: (sweep[w]["hit_at_1"], sweep[w]["hit_at_3"], -w))
    results["hybrid"] = {**sweep[best_w], "keyword_weight": best_w}

    print(f"{len(rows)} queries\n")
    print(f"{'mode':<12}{'hit@1':>8}{'hit@3':>8}   per-language hit@1")
    for mode in ("keyword", "embedding", "hybrid"):
        r = results[mode]
        langs = "  ".join(f"{k} {v:.2f}" for k, v in r["per_language_hit_at_1"].items())
        print(f"{mode:<12}{r['hit_at_1']:>8.3f}{r['hit_at_3']:>8.3f}   {langs}")
    print("\nhybrid weight sweep (hit@1/hit@3): " + "  ".join(
        f"{w}: {sweep[w]['hit_at_1']:.3f}/{sweep[w]['hit_at_3']:.3f}" for w in sweep))
    print(f"chosen keyword weight: {best_w}")
    print("\nhybrid misses:")
    for m in results["hybrid"]["misses"]:
        print(f"  {m['text']}  expected {m['expected']}  got {m['got']}")

    report = {
        "n_queries": len(rows),
        "embedding_model": embedder.model_name,
        "results": results,
        "weight_sweep": {str(w): {"hit_at_1": v["hit_at_1"], "hit_at_3": v["hit_at_3"]}
                         for w, v in sweep.items()},
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
