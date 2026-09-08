# -*- coding: utf-8 -*-
"""Score the keyword baseline on the hand-written test set.

This is the number ml/train_intent.py has to beat, and the "rules only" row in
the ablation table in docs/RESULTS.md. Runs without torch.

    python ml/eval_baseline.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django  # noqa: E402

django.setup()

from ai.local.intent import KeywordIntentBaseline  # noqa: E402

TEST_PATH = ROOT / "ml" / "data" / "intent_test_handwritten.jsonl"


def main() -> None:
    rows = [
        json.loads(line)
        for line in TEST_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    clf = KeywordIntentBaseline()

    correct = 0
    per_intent = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    per_language: Counter = Counter()
    per_language_total: Counter = Counter()
    mistakes: list[tuple[str, str, str]] = []

    for row in rows:
        pred = clf.predict(row["text"], row["language"]).intent
        gold = row["intent"]
        per_language_total[row["language"]] += 1
        if pred == gold:
            correct += 1
            per_intent[gold]["tp"] += 1
            per_language[row["language"]] += 1
        else:
            per_intent[gold]["fn"] += 1
            per_intent[pred]["fp"] += 1
            mistakes.append((row["text"], gold, pred))

    total = len(rows)
    print(f"Keyword baseline on {total} hand-written examples")
    print(f"  accuracy: {correct}/{total} = {correct / total:.3f}\n")

    print("  per language:")
    for lang in sorted(per_language_total):
        n = per_language_total[lang]
        print(f"    {lang}: {per_language[lang]:>3}/{n:<3} = {per_language[lang] / n:.3f}")

    print("\n  per intent (P / R / F1):")
    f1s = []
    for intent in sorted(per_intent):
        stats = per_intent[intent]
        tp, fp, fn = stats["tp"], stats["fp"], stats["fn"]
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        f1s.append(f1)
        print(f"    {intent:<22} {precision:.2f} / {recall:.2f} / {f1:.2f}   (n={tp + fn})")
    print(f"\n  macro F1: {sum(f1s) / len(f1s):.3f}")

    print(f"\n  {len(mistakes)} mistakes (first 20):")
    for text, gold, pred in mistakes[:20]:
        print(f"    {gold:<20} -> {pred:<20} | {text}")

    out = ROOT / "ml" / "reports" / "baseline_intent_metrics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "model": "keyword_baseline",
                "test_set": "intent_test_handwritten.jsonl",
                "n": total,
                "accuracy": round(correct / total, 4),
                "macro_f1": round(sum(f1s) / len(f1s), 4),
                "per_language": {
                    lang: round(per_language[lang] / per_language_total[lang], 4)
                    for lang in per_language_total
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n  wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
