"""Choose INTENT_MIN_CONFIDENCE from data instead of from taste.

The app refuses to act on an intent whose softmax confidence is below
``settings.INTENT_MIN_CONFIDENCE``; below it, the reply is "I did not catch
that" and the user is shown the icon grid instead. That threshold decides two
things at once, and they pull in opposite directions:

  · How often the app acts on the wrong intent. In a money app this is the
    expensive failure. Sending 500 rupees to the wrong person because
    "purana hisaab dikha do" was read as check_balance is not recoverable by
    apologising.
  · How often the app refuses a request it actually understood. This is the
    cheap failure -- the user taps an icon -- but it is the one they feel, and
    enough of it makes the voice interface pointless.

So the threshold is not a style choice. It is picked here by sweeping it over
the hand-written test set and reading three numbers off the sweep:

  coverage        fraction of utterances the app is willing to act on
  accepted_error  of those, the fraction where it acts on the wrong intent
  silent_error    accepted AND wrong, as a fraction of ALL utterances --
                  the one that actually costs the user something

The recommendation maximises coverage subject to silent_error <= BUDGET.
That ordering is the whole argument: refusing is recoverable, acting is not.

Run after training:

    python ml/calibrate_gate.py

Writes ml/reports/intent_gate.json and prints the table.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

# The report is UTF-8 whatever the console is, but the table printed below
# contains Devanagari, Tamil and Telugu, and a Windows console defaults to
# cp1252. Without this the script dies on print() after doing all the work.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

from data.taxonomy import LABEL2ID  # noqa: E402

DATA = ROOT / "ml" / "data"
REPORTS = ROOT / "ml" / "reports"
ARTIFACT = ROOT / "ml" / "artifacts" / "intent"

# Of every hundred things the user says, how many may the app act on wrongly?
# Five is already generous for a payment surface; it is set here rather than
# inferred so that changing it is a visible decision in the diff.
BUDGET = 0.05

THRESHOLDS = [round(0.05 * i, 2) for i in range(2, 19)]  # 0.10 .. 0.90


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def score(model_dir: Path, rows: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (gold, pred, confidence) over rows."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device).eval()

    gold = np.array([LABEL2ID[r["intent"]] for r in rows])
    preds = np.zeros(len(rows), dtype=int)
    confidences = np.zeros(len(rows), dtype=float)

    with torch.no_grad():
        for start in range(0, len(rows), 32):
            batch = [r["text"] for r in rows[start : start + 32]]
            encoded = tokenizer(
                batch, return_tensors="pt", padding=True, truncation=True, max_length=64
            ).to(device)
            probs = torch.softmax(model(**encoded).logits, dim=-1)
            top = torch.max(probs, dim=-1)
            preds[start : start + len(batch)] = top.indices.cpu().numpy()
            confidences[start : start + len(batch)] = top.values.cpu().numpy()

    return gold, preds, confidences


def sweep(gold: np.ndarray, pred: np.ndarray, conf: np.ndarray) -> list[dict]:
    total = len(gold)
    correct = pred == gold
    rows = []
    for tau in THRESHOLDS:
        accepted = conf >= tau
        n_accepted = int(accepted.sum())
        n_silent = int((accepted & ~correct).sum())
        rows.append({
            "threshold": tau,
            "coverage": round(n_accepted / total, 4),
            "accepted_n": n_accepted,
            "accepted_accuracy": round(float(correct[accepted].mean()), 4) if n_accepted else None,
            "accepted_error": round(1 - float(correct[accepted].mean()), 4) if n_accepted else None,
            "silent_error": round(n_silent / total, 4),
            "fallback_rate": round(1 - n_accepted / total, 4),
        })
    return rows


def recommend(rows: list[dict]) -> dict:
    """Highest coverage among thresholds that keep silent_error within budget."""
    affordable = [r for r in rows if r["silent_error"] <= BUDGET]
    if not affordable:
        # Nothing meets the budget: take the strictest threshold measured and
        # say so plainly rather than returning a number that implies it does.
        return {**rows[-1], "meets_budget": False}
    return {**max(affordable, key=lambda r: r["coverage"]), "meets_budget": True}


def main() -> None:
    if not (ARTIFACT / "config.json").exists():
        raise SystemExit(f"No model artifact at {ARTIFACT}. Run ml/train_intent.py first.")

    rows = load_jsonl(DATA / "intent_test_handwritten.jsonl")
    gold, pred, conf = score(ARTIFACT, rows)
    table = sweep(gold, pred, conf)
    best = recommend(table)

    correct = pred == gold
    print(f"\n{len(rows)} hand-written utterances | overall accuracy {correct.mean():.4f}")
    print(f"mean confidence  right {conf[correct].mean():.3f}  "
          f"wrong {conf[~correct].mean():.3f}\n")
    print(f"{'tau':>6} {'coverage':>9} {'acc|accepted':>13} {'silent err':>11} {'fallback':>9}")
    for row in table:
        mark = "  <-- recommended" if row["threshold"] == best["threshold"] else ""
        acc = f"{row['accepted_accuracy']:.4f}" if row["accepted_accuracy"] is not None else "   n/a"
        print(f"{row['threshold']:>6.2f} {row['coverage']:>9.4f} {acc:>13} "
              f"{row['silent_error']:>11.4f} {row['fallback_rate']:>9.4f}{mark}")

    if not best["meets_budget"]:
        print(f"\nWARNING: no threshold keeps silent error within {BUDGET:.0%}. "
              f"The model is not accurate enough to act unsupervised on this test set.")

    report = {
        "model": "muril_intent",
        "test_set": "intent_test_handwritten.jsonl",
        "n": len(rows),
        "accuracy": round(float(correct.mean()), 4),
        "mean_confidence_right": round(float(conf[correct].mean()), 4),
        "mean_confidence_wrong": round(float(conf[~correct].mean()), 4),
        "silent_error_budget": BUDGET,
        "recommended_threshold": best["threshold"],
        "recommended": best,
        "sweep": table,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / "intent_gate.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwrote {out.relative_to(ROOT)}")
    print(f"set INTENT_MIN_CONFIDENCE={best['threshold']} in backend/config/settings/base.py "
          f"(or the INTENT_MIN_CONFIDENCE env var)")


if __name__ == "__main__":
    main()
