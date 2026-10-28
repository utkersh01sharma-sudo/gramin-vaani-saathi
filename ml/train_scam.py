# -*- coding: utf-8 -*-
"""Train ScamNet: MuRIL fine-tune + rule-feature model, blended, with an ablation.

    python ml/data/generate_scam_data.py     # once
    python ml/train_scam.py                  # train both halves, evaluate, save
    python ml/train_scam.py --eval-only      # re-score the artifacts on disk

Three systems are scored on the hand-written test set:

  rules only        multinomial logistic regression on ai/local/scam_rules.py
  transformer only  MuRIL fine-tuned on the generated corpus
  blended           w * transformer + (1 - w) * rules, as 3-class probabilities

The blend weight is fixed at 0.7 *before* looking at the test set -- it is the
value in the original design. The script also prints accuracy for every weight
from 0 to 1 so the reader can see the shape of the curve, but that curve is
reported, not used for selection: choosing w on the same 83 rows we report
would quietly turn the test set into a validation set.

The number that matters most is **precision on the scam class**. A false alarm
on a genuine bank message teaches the user to ignore the warning, and a warning
people ignore protects nobody.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from ai.local import scam_rules  # noqa: E402  (pure python, no Django needed)

DATA = ROOT / "ml" / "data"
ARTIFACTS = ROOT / "ml" / "artifacts" / "scam"
REPORTS = ROOT / "ml" / "reports"
BASE_MODEL = "google/muril-base-cased"
CLASSES = ["safe", "suspicious", "scam"]
LABEL2ID = {c: i for i, c in enumerate(CLASSES)}
BLEND_W = 0.7


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    import torch

    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# ------------------------------------------------------------------ rules half
def featurise(rows: list[dict]) -> np.ndarray:
    return np.array([[scam_rules.extract(r["text"])[f] for f in scam_rules.FEATURES] for r in rows])


def fit_rules(train_rows: list[dict]) -> dict:
    from sklearn.linear_model import LogisticRegression

    X = featurise(train_rows)
    y = np.array([LABEL2ID[r["label"]] for r in train_rows])
    # C=1.0 with 17 binary features and 8k rows is barely regularised; the
    # point is interpretable weights, not squeezing the last point out.
    clf = LogisticRegression(max_iter=2000, C=1.0)
    clf.fit(X, y)
    # Per-feature "how much does this push towards scam rather than safe".
    # This ordering is what decides which reason is spoken first.
    toward_scam = clf.coef_[LABEL2ID["scam"]] - clf.coef_[LABEL2ID["safe"]]
    return {
        "features": scam_rules.FEATURES,
        "classes": CLASSES,
        "coef": clf.coef_.tolist(),
        "intercept": clf.intercept_.tolist(),
        "toward_scam": dict(zip(scam_rules.FEATURES, np.round(toward_scam, 4).tolist())),
    }


def rules_proba(params: dict, rows: list[dict]) -> np.ndarray:
    X = featurise(rows)
    z = X @ np.array(params["coef"]).T + np.array(params["intercept"])
    z -= z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


# ------------------------------------------------------------------ transformer half
def model_proba(model_dir: Path, rows: list[dict], batch_size: int = 32) -> tuple[np.ndarray, float]:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device).eval()
    out = []
    started = time.perf_counter()
    with torch.no_grad():
        for start in range(0, len(rows), batch_size):
            batch = [r["text"] for r in rows[start : start + batch_size]]
            enc = tokenizer(batch, return_tensors="pt", padding=True, truncation=True,
                            max_length=128).to(device)
            out.append(torch.softmax(model(**enc).logits, dim=-1).cpu().numpy())
    ms = (time.perf_counter() - started) * 1000 / max(len(rows), 1)
    return np.concatenate(out), ms


def train_transformer(args, train_rows, val_rows) -> None:
    import torch
    from datasets import Dataset
    from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                              DataCollatorWithPadding, Trainer, TrainingArguments)

    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.base_model, num_labels=len(CLASSES),
        id2label=dict(enumerate(CLASSES)), label2id=LABEL2ID,
    )
    # Same reasoning as train_intent.py: the 152M-parameter embedding matrix is
    # 64% of MuRIL, and training it is what pushes an 8 GB card into shared
    # memory beside a browser. Measured there: +1.1pt accuracy for full
    # fine-tuning. Pass --train-embeddings for the same comparison here.
    if not args.train_embeddings:
        for p in model.base_model.embeddings.parameters():
            p.requires_grad = False

    def ds(rows):
        d = Dataset.from_dict({"text": [r["text"] for r in rows],
                               "labels": [LABEL2ID[r["label"]] for r in rows]})
        return d.map(lambda b: tokenizer(b["text"], truncation=True, max_length=args.max_length),
                     batched=True, remove_columns=["text"])

    def metrics(pred):
        from sklearn.metrics import f1_score

        logits, labels = pred
        return {"macro_f1": f1_score(labels, logits.argmax(-1), average="macro")}

    cuda = torch.cuda.is_available()
    targs = TrainingArguments(
        output_dir=str(ROOT / "ml" / "artifacts" / "_scam_checkpoints"),
        num_train_epochs=args.epochs, per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=32, gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr, warmup_ratio=0.1, weight_decay=0.01,
        eval_strategy="epoch", save_strategy="epoch", load_best_model_at_end=True,
        metric_for_best_model="macro_f1", save_total_limit=1, logging_steps=100,
        fp16=cuda, report_to=[], seed=args.seed,
    )
    trainer = Trainer(model=model, args=targs, train_dataset=ds(train_rows),
                      eval_dataset=ds(val_rows), tokenizer=tokenizer,
                      data_collator=DataCollatorWithPadding(tokenizer), compute_metrics=metrics)
    # MuRIL ships 73 non-contiguous tensors; safetensors refuses them at the first
    # checkpoint, after an epoch of compute. Pack them before training starts.
    for p in model.parameters():
        if not p.data.is_contiguous():
            p.data = p.data.contiguous()
    started = time.time()
    trainer.train()
    minutes = (time.time() - started) / 60
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    for p in trainer.model.parameters():
        if not p.data.is_contiguous():
            p.data = p.data.contiguous()
    trainer.save_model(str(ARTIFACTS))
    tokenizer.save_pretrained(str(ARTIFACTS))
    (ARTIFACTS / "train_info.json").write_text(json.dumps({
        "train_minutes": round(minutes, 2), "epochs": args.epochs, "lr": args.lr,
        "embeddings_frozen": not args.train_embeddings, "n_train": len(train_rows),
    }, indent=2), encoding="utf-8")
    print(f"trained in {minutes:.1f} min -> {ARTIFACTS}")


# ------------------------------------------------------------------ scoring
def score_system(proba: np.ndarray, gold: np.ndarray) -> dict:
    from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support

    pred = proba.argmax(1)
    p, r, f, s = precision_recall_fscore_support(gold, pred, labels=[0, 1, 2], zero_division=0)
    # Binary view: is the message flagged at all (suspicious or scam)?
    flagged_pred, flagged_gold = pred > 0, gold > 0
    return {
        "accuracy": round(float(accuracy_score(gold, pred)), 4),
        "macro_f1": round(float(f1_score(gold, pred, average="macro")), 4),
        "per_class": {CLASSES[i]: {"precision": round(float(p[i]), 4), "recall": round(float(r[i]), 4),
                                   "f1": round(float(f[i]), 4), "support": int(s[i])} for i in range(3)},
        "scam_precision": round(float(p[2]), 4),
        "scam_recall": round(float(r[2]), 4),
        # The cost that matters for trust: genuine messages wrongly flagged.
        "false_alarm_rate_on_safe": round(float((flagged_pred & ~flagged_gold).sum() / max((~flagged_gold).sum(), 1)), 4),
        "missed_scams": int(((gold == 2) & (pred == 0)).sum()),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=float, default=3)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--grad-accum", type=int, default=1)
    ap.add_argument("--lr", type=float, default=3e-5)
    ap.add_argument("--max-length", type=int, default=96)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--train-embeddings", action="store_true")
    ap.add_argument("--base-model", default=BASE_MODEL)
    ap.add_argument("--eval-only", action="store_true")
    args = ap.parse_args()
    set_seed(args.seed)

    train_rows = load_jsonl(DATA / "scam_train.jsonl")
    val_rows = load_jsonl(DATA / "scam_val.jsonl")
    test_rows = load_jsonl(DATA / "scam_test_handwritten.jsonl")
    print(f"train {len(train_rows)} | val {len(val_rows)} | test {len(test_rows)} (hand-written)")
    print("test by class:", dict(Counter(r["label"] for r in test_rows)),
          "| by language:", dict(Counter(r["language"] for r in test_rows)))

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    rules_path = ARTIFACTS / "rules.json"
    if args.eval_only and rules_path.exists():
        params = json.loads(rules_path.read_text(encoding="utf-8"))
    else:
        params = fit_rules(train_rows)
        rules_path.write_text(json.dumps(params, indent=2), encoding="utf-8")
        print("\nrule weights toward scam (fitted):")
        for k, v in sorted(params["toward_scam"].items(), key=lambda kv: -kv[1]):
            print(f"  {k:<18} {v:+.2f}")

    if not args.eval_only:
        train_transformer(args, train_rows, val_rows)

    gold = np.array([LABEL2ID[r["label"]] for r in test_rows])
    p_rules = rules_proba(params, test_rows)
    p_model, ms = model_proba(ARTIFACTS, test_rows)
    p_blend = BLEND_W * p_model + (1 - BLEND_W) * p_rules

    systems = {
        "rules_only": score_system(p_rules, gold),
        "transformer_only": score_system(p_model, gold),
        f"blended_w{BLEND_W}": score_system(p_blend, gold),
    }
    curve = {}
    for w in np.round(np.linspace(0, 1, 11), 1):
        s = score_system(w * p_model + (1 - w) * p_rules, gold)
        curve[str(w)] = {"accuracy": s["accuracy"], "macro_f1": s["macro_f1"],
                         "scam_precision": s["scam_precision"]}

    # Validation on generated data, for completeness and to show the gap.
    p_val = BLEND_W * model_proba(ARTIFACTS, val_rows)[0] + (1 - BLEND_W) * rules_proba(params, val_rows)
    val_gold = np.array([LABEL2ID[r["label"]] for r in val_rows])
    val_acc = float((p_val.argmax(1) == val_gold).mean())

    pred = p_blend.argmax(1)
    per_language = {lang: round(float((pred[m] == gold[m]).mean()), 4)
                    for lang in ("hi", "en", "ta", "te")
                    for m in [np.array([r["language"] == lang for r in test_rows])]}
    mistakes = [{"text": test_rows[i]["text"], "language": test_rows[i]["language"],
                 "gold": CLASSES[gold[i]], "pred": CLASSES[pred[i]],
                 "p_model": np.round(p_model[i], 3).tolist(), "p_rules": np.round(p_rules[i], 3).tolist()}
                for i in range(len(test_rows)) if pred[i] != gold[i]]

    print(f"\n{'=' * 72}\nScamNet ablation on {len(test_rows)} hand-written messages\n{'=' * 72}")
    print(f"{'system':<20}{'acc':>7}{'macroF1':>9}{'scamP':>8}{'scamR':>8}{'falseAlarm':>12}{'missed':>8}")
    for name, s in systems.items():
        print(f"{name:<20}{s['accuracy']:>7.3f}{s['macro_f1']:>9.3f}{s['scam_precision']:>8.3f}"
              f"{s['scam_recall']:>8.3f}{s['false_alarm_rate_on_safe']:>12.3f}{s['missed_scams']:>8}")
    print("\nblend weight curve (reported, not used for selection):")
    print("  " + "  ".join(f"{w}:{v['macro_f1']:.3f}" for w, v in curve.items()))
    print(f"\nper language (blended): {per_language}")
    print(f"val accuracy on generated data: {val_acc:.4f}  (measures the generator, not the world)")
    print(f"latency: {ms:.1f} ms / message")
    print(f"\n{len(mistakes)} mistakes:")
    for m in mistakes:
        print(f"  [{m['language']}] {m['gold']:<10} -> {m['pred']:<10} | {m['text'][:90]}")

    info_path = ARTIFACTS / "train_info.json"
    info = json.loads(info_path.read_text(encoding="utf-8")) if info_path.exists() else {}
    report = {
        "model": "scamnet", "base_model": BASE_MODEL, "classes": CLASSES,
        "blend_weight_transformer": BLEND_W, "n_test": len(test_rows),
        "n_train": len(train_rows), "val_accuracy_generated": round(val_acc, 4),
        "systems": systems, "blend_curve": curve, "per_language_blended": per_language,
        "inference_ms_per_message": round(ms, 2), "train": info,
        "rule_weights_toward_scam": params["toward_scam"], "mistakes": mistakes,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "scam_metrics.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                              encoding="utf-8")
    print(f"\nwrote ml/reports/scam_metrics.json")


if __name__ == "__main__":
    main()
