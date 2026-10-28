"""Measure the fraud-question search and choose its no-answer threshold.

    python ml/eval_fraud_qa.py

40 hand-written in-domain questions (10 per language) phrased differently from
the knowledge base, plus 8 off-topic ones (weather, cricket, recipes) that must
get "no good answer" rather than their least-bad match.

The threshold is chosen to answer as many in-domain questions correctly as
possible while answering *none* of the off-topic ones: confidently answering
"what is the weather" with advice about OTPs is the failure that makes people
stop trusting the box.

Writes ml/reports/fraud_qa.json.
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
from apps.fraud import knowledge  # noqa: E402

QUERIES = ROOT / "ml" / "data" / "fraud_questions.jsonl"
OUT = ROOT / "ml" / "reports" / "fraud_qa.json"


def main() -> None:
    rows = [json.loads(l) for l in QUERIES.read_text(encoding="utf-8").splitlines() if l.strip()]
    inside = [r for r in rows if r["relevant"]]
    outside = [r for r in rows if not r["relevant"]]
    embedder = Embedder()

    def ranked(mode):
        return [(r, knowledge.score_all(r["text"], embedder, mode=mode)) for r in rows]

    results = {}
    for mode in ("keyword", "embedding", "hybrid"):
        rk = ranked(mode)
        h1 = [rank[0][0]["id"] in r["relevant"] for r, rank in rk if r["relevant"]]
        h3 = [any(e["id"] in r["relevant"] for e, _ in rank[:3]) for r, rank in rk if r["relevant"]]
        results[mode] = {"hit_at_1": round(sum(h1) / len(h1), 4), "hit_at_3": round(sum(h3) / len(h3), 4)}

    # Threshold sweep on the deployed (hybrid) scores.
    rk = ranked("hybrid")
    best_in = [(rank[0][1], rank[0][0]["id"] in r["relevant"]) for r, rank in rk if r["relevant"]]
    best_out = [rank[0][1] for r, rank in rk if not r["relevant"]]
    sweep = []
    for t in [round(0.80 + 0.005 * i, 3) for i in range(17)]:
        answered_right = sum(1 for s, ok in best_in if s >= t and ok) / len(best_in)
        answered_wrong = sum(1 for s, ok in best_in if s >= t and not ok) / len(best_in)
        offtopic_answered = sum(1 for s in best_out if s >= t) / len(best_out)
        sweep.append({"threshold": t, "answered_right": round(answered_right, 4),
                      "answered_wrong": round(answered_wrong, 4),
                      "offtopic_answered": round(offtopic_answered, 4)})
    safe = [s for s in sweep if s["offtopic_answered"] == 0]
    chosen = max(safe, key=lambda s: (s["answered_right"], -s["answered_wrong"])) if safe else sweep[-1]

    misses = [{"text": r["text"], "expected": r["relevant"], "got": rank[0][0]["id"], "score": round(rank[0][1], 4)}
              for r, rank in rk if r["relevant"] and rank[0][0]["id"] not in r["relevant"]]

    print(f"{len(inside)} in-domain, {len(outside)} off-topic questions\n")
    for mode, m in results.items():
        print(f"{mode:<10} hit@1 {m['hit_at_1']:.3f}  hit@3 {m['hit_at_3']:.3f}")
    print(f"\noff-topic best scores: {sorted(round(s, 3) for s in best_out)}")
    print(f"in-domain best scores (min/median): {min(s for s, _ in best_in):.3f} / "
          f"{sorted(s for s, _ in best_in)[len(best_in) // 2]:.3f}")
    print("\nthreshold  right   wrong   off-topic answered")
    for s in sweep:
        mark = "  <- chosen" if s is chosen else ""
        print(f"  {s['threshold']:.3f}   {s['answered_right']:.3f}   {s['answered_wrong']:.3f}   "
              f"{s['offtopic_answered']:.3f}{mark}")
    print("\nhybrid misses:")
    for m in misses:
        print(f"  {m['text']}  expected {m['expected']}  got {m['got']} ({m['score']})")

    OUT.write_text(json.dumps({
        "n_in_domain": len(inside), "n_off_topic": len(outside), "n_entries": len(knowledge.load_entries()),
        "embedding_model": embedder.model_name, "keyword_weight": knowledge.KEYWORD_WEIGHT,
        "results": results, "threshold_sweep": sweep, "chosen_threshold": chosen, "misses": misses,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
