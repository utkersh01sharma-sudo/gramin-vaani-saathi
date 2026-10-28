# -*- coding: utf-8 -*-
"""Fine-tune MuRIL for 14-way intent classification across hi / en / ta / te.

    python ml/train_intent.py                 # train, evaluate, save
    python ml/train_intent.py --epochs 5      # override any hyperparameter
    python ml/train_intent.py --eval-only     # score an artifact already on disk

Why MuRIL and not IndicBERT or XLM-R: MuRIL is pre-trained on 17 Indian languages
*and on their transliterated forms*. A rural user typing or dictating "paise
bhejo" in Latin script is a first-class input here, not an edge case, and that is
exactly what MuRIL's pre-training covers and IndicBERT's does not.

The number that matters is printed at the end: accuracy on
``intent_test_handwritten.jsonl``, which was written by hand and shares no
templates with the training data. Validation accuracy on generated data is close
to meaningless -- it measures how well the model learned the generator.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ml"))

from data.taxonomy import ID2LABEL, INTENTS, LABEL2ID  # noqa: E402

DATA = ROOT / "ml" / "data"
ARTIFACTS = ROOT / "ml" / "artifacts" / "intent"
REPORTS = ROOT / "ml" / "reports"

BASE_MODEL = "google/muril-base-cased"


def set_seed(seed: int) -> None:
    """Pin every source of randomness so a reported number can be reproduced."""
    random.seed(seed)
    np.random.seed(seed)
    import torch

    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def build_dataset(rows: list[dict], tokenizer, max_length: int):
    from datasets import Dataset

    dataset = Dataset.from_dict(
        {
            "text": [r["text"] for r in rows],
            "labels": [LABEL2ID[r["intent"]] for r in rows],
        }
    )
    return dataset.map(
        lambda batch: tokenizer(batch["text"], truncation=True, max_length=max_length),
        batched=True,
        remove_columns=["text"],
    )


def compute_metrics(eval_pred):
    from sklearn.metrics import accuracy_score, f1_score

    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "macro_f1": f1_score(labels, preds, average="macro", zero_division=0),
    }


# ------------------------------------------------------------------ evaluation
def evaluate_artifact(model_dir: Path, rows: list[dict], batch_size: int = 32) -> dict:
    """Score a saved artifact on held-out rows. Returns the full report dict."""
    import torch
    from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device).eval()

    texts = [r["text"] for r in rows]
    gold = np.array([LABEL2ID[r["intent"]] for r in rows])
    preds = np.zeros(len(rows), dtype=int)
    confidences = np.zeros(len(rows), dtype=float)

    started = time.perf_counter()
    with torch.no_grad():
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            encoded = tokenizer(
                batch, return_tensors="pt", padding=True, truncation=True, max_length=64
            ).to(device)
            probs = torch.softmax(model(**encoded).logits, dim=-1)
            top = torch.max(probs, dim=-1)
            preds[start : start + len(batch)] = top.indices.cpu().numpy()
            confidences[start : start + len(batch)] = top.values.cpu().numpy()
    elapsed_ms = (time.perf_counter() - started) * 1000

    accuracy = float((preds == gold).mean())
    macro_f1 = float(f1_score(gold, preds, average="macro", zero_division=0))

    per_language: dict[str, float] = {}
    for language in sorted({r["language"] for r in rows}):
        mask = np.array([r["language"] == language for r in rows])
        per_language[language] = float((preds[mask] == gold[mask]).mean())

    precision, recall, f1, support = precision_recall_fscore_support(
        gold, preds, labels=list(range(len(INTENTS))), zero_division=0
    )
    per_intent = {
        INTENTS[i]: {
            "precision": round(float(precision[i]), 4),
            "recall": round(float(recall[i]), 4),
            "f1": round(float(f1[i]), 4),
            "support": int(support[i]),
        }
        for i in range(len(INTENTS))
    }

    mistakes = [
        {"text": rows[i]["text"], "language": rows[i]["language"],
         "gold": ID2LABEL[int(gold[i])], "pred": ID2LABEL[int(preds[i])],
         "confidence": round(float(confidences[i]), 3)}
        for i in range(len(rows)) if preds[i] != gold[i]
    ]

    return {
        "model": "muril_intent",
        "base_model": BASE_MODEL,
        "device": device,
        "n": len(rows),
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "per_language": {k: round(v, 4) for k, v in per_language.items()},
        "per_intent": per_intent,
        "mean_confidence": round(float(confidences.mean()), 4),
        # Confidence on the rows it got wrong. If this is high the model is
        # confidently wrong, and INTENT_MIN_CONFIDENCE will not catch anything.
        "mean_confidence_when_wrong": (
            round(float(np.mean([m["confidence"] for m in mistakes])), 4) if mistakes else None
        ),
        "inference_ms_per_utterance": round(elapsed_ms / max(len(rows), 1), 2),
        "confusion_matrix": confusion_matrix(
            gold, preds, labels=list(range(len(INTENTS)))
        ).tolist(),
        "labels": INTENTS,
        "mistakes": mistakes,
    }


def print_report(report: dict, baseline: dict | None) -> None:
    print(f"\n{'=' * 66}")
    print(f"IntentNet on {report['n']} hand-written examples ({report['device']})")
    print("=" * 66)
    print(f"  accuracy : {report['accuracy']:.3f}")
    print(f"  macro F1 : {report['macro_f1']:.3f}")
    print(f"  latency  : {report['inference_ms_per_utterance']:.1f} ms / utterance")

    if baseline:
        delta_acc = report["accuracy"] - baseline["accuracy"]
        delta_f1 = report["macro_f1"] - baseline["macro_f1"]
        print(f"\n  vs keyword baseline ({baseline['accuracy']:.3f} acc / "
              f"{baseline['macro_f1']:.3f} F1):")
        print(f"    accuracy {delta_acc:+.3f}   macro F1 {delta_f1:+.3f}")

    print("\n  per language:")
    for language, score in sorted(report["per_language"].items()):
        bar = "#" * int(score * 30)
        base = baseline["per_language"].get(language) if baseline else None
        suffix = f"   (baseline {base:.3f})" if base is not None else ""
        print(f"    {language}: {score:.3f} {bar:<30}{suffix}")

    print("\n  per intent (P / R / F1, n):")
    for intent, stats in report["per_intent"].items():
        print(f"    {intent:<22} {stats['precision']:.2f} / {stats['recall']:.2f} / "
              f"{stats['f1']:.2f}   (n={stats['support']})")

    print(f"\n  mean confidence: {report['mean_confidence']:.3f}"
          f" | when wrong: {report['mean_confidence_when_wrong']}")

    mistakes = report["mistakes"]
    print(f"\n  {len(mistakes)} mistakes"
          f"{' (first 15)' if len(mistakes) > 15 else ''}:")
    for mistake in mistakes[:15]:
        print(f"    [{mistake['language']}] {mistake['gold']:<20} -> "
              f"{mistake['pred']:<20} ({mistake['confidence']:.2f}) | {mistake['text']}")


# ------------------------------------------------------------------ main
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=float, default=4)
    parser.add_argument("--batch-size", type=int, default=8)
    # The 4070 has 8 GB, and a desktop session with a browser open is already
    # holding 2-3 GB of it. Batch 8 x 2 accumulation trains at an effective
    # batch of 16 without competing with the machine the demo runs on.
    parser.add_argument("--grad-accum", type=int, default=2)
    # Freeze the embedding matrix. MuRIL's vocabulary is 197k wordpieces, so its
    # embeddings are 152M of the model's 238M parameters -- 64% of it. Training
    # them costs 1.8 GB of gradient and Adam state for no benefit we can measure:
    # those vectors were pre-trained on 17 Indian languages and their
    # transliterations, which is exactly the distribution we are fine-tuning on,
    # and 6.7k rows is far too little to improve them without drifting the
    # under-represented languages. Measured on the 4070: peak 4.45 GB unfrozen
    # against 2.8 GB frozen. That difference decides whether the run fits in VRAM
    # beside a browser or silently spills into shared system memory, where a step
    # takes 76 seconds instead of 0.14 -- a 500x slowdown that looks like a hang,
    # not an error. Pass --train-embeddings to compare.
    parser.add_argument("--train-embeddings", action="store_true",
                        help="Fine-tune the 152M-parameter embedding matrix too.")
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=64)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--base-model", default=BASE_MODEL)
    parser.add_argument("--output", default=str(ARTIFACTS))
    parser.add_argument("--eval-only", action="store_true",
                        help="Skip training; score the artifact already at --output.")
    args = parser.parse_args()

    set_seed(args.seed)
    output_dir = Path(args.output)
    test_rows = load_jsonl(DATA / "intent_test_handwritten.jsonl")

    baseline_path = REPORTS / "baseline_intent_metrics.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8")) if baseline_path.exists() else None

    if not args.eval_only:
        import torch
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
            DataCollatorWithPadding,
            Trainer,
            TrainingArguments,
        )

        train_rows = load_jsonl(DATA / "intent_train.jsonl")
        val_rows = load_jsonl(DATA / "intent_val.jsonl")

        print(f"train {len(train_rows)} | val {len(val_rows)} | test {len(test_rows)}")
        print("train by language:", dict(Counter(r["language"] for r in train_rows)))
        print("train by script  :", dict(Counter(r.get("script", "?") for r in train_rows)))

        cuda = torch.cuda.is_available()
        print(f"\ndevice: {torch.cuda.get_device_name(0) if cuda else 'cpu'}")
        print(f"loading {args.base_model} ...")

        tokenizer = AutoTokenizer.from_pretrained(args.base_model)
        model = AutoModelForSequenceClassification.from_pretrained(
            args.base_model,
            num_labels=len(INTENTS),
            id2label=ID2LABEL,
            label2id=LABEL2ID,
        )

        if not args.train_embeddings:
            for param in model.base_model.embeddings.parameters():
                param.requires_grad = False
        trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
        total = sum(p.numel() for p in model.parameters())
        print(f"trainable {trainable / 1e6:.1f}M of {total / 1e6:.1f}M parameters "
              f"({100 * trainable / total:.0f}%)")

        train_ds = build_dataset(train_rows, tokenizer, args.max_length)
        val_ds = build_dataset(val_rows, tokenizer, args.max_length)

        training_args = TrainingArguments(
            output_dir=str(ROOT / "ml" / "artifacts" / "_intent_checkpoints"),
            num_train_epochs=args.epochs,
            per_device_train_batch_size=args.batch_size,
            per_device_eval_batch_size=32,
            gradient_accumulation_steps=args.grad_accum,
            learning_rate=args.lr,
            warmup_ratio=0.1,
            weight_decay=0.01,
            eval_strategy="epoch",
            save_strategy="epoch",
            load_best_model_at_end=True,
            metric_for_best_model="macro_f1",
            greater_is_better=True,
            save_total_limit=1,
            logging_steps=50,
            fp16=cuda,          # halves memory on the 4070; no accuracy cost here
            report_to=[],
            seed=args.seed,
            disable_tqdm=False,
        )

        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=train_ds,
            eval_dataset=val_ds,
            data_collator=DataCollatorWithPadding(tokenizer),
            compute_metrics=compute_metrics,
        )

        # safetensors refuses to write a tensor whose storage is not contiguous,
        # and it raises at the first epoch-end checkpoint -- after the epoch has
        # already been paid for. MuRIL arrives from the hub with several
        # attention projections sharing a strided view, which is harmless for
        # the forward pass and fatal for the writer. Pack them once, here, where
        # it costs nothing, instead of discovering it 20 minutes in.
        for param in model.parameters():
            if not param.data.is_contiguous():
                param.data = param.data.contiguous()

        started = time.perf_counter()
        trainer.train()
        minutes = (time.perf_counter() - started) / 60

        val_metrics = trainer.evaluate()
        print(f"\ntrained in {minutes:.1f} min")
        print(f"validation (generated data): acc {val_metrics['eval_accuracy']:.4f} "
              f"| macro F1 {val_metrics['eval_macro_f1']:.4f}")

        output_dir.mkdir(parents=True, exist_ok=True)
        for param in trainer.model.parameters():
            if not param.data.is_contiguous():
                param.data = param.data.contiguous()
        trainer.save_model(str(output_dir))
        tokenizer.save_pretrained(str(output_dir))
        print(f"saved to {output_dir}")

    if not (output_dir / "config.json").exists():
        raise SystemExit(f"No model artifact at {output_dir}. Train first.")

    # The honest number: hand-written rows, zero template overlap with training.
    report = evaluate_artifact(output_dir, test_rows)
    if not args.eval_only:
        report["train_minutes"] = round(minutes, 2)
        report["hyperparameters"] = {
            "epochs": args.epochs, "batch_size": args.batch_size,
            "grad_accum": args.grad_accum, "lr": args.lr,
            "max_length": args.max_length, "seed": args.seed,
            "embeddings_frozen": not args.train_embeddings,
        }
        report["validation_generated"] = {
            "accuracy": round(float(val_metrics["eval_accuracy"]), 4),
            "macro_f1": round(float(val_metrics["eval_macro_f1"]), 4),
        }
    if baseline:
        report["baseline"] = {
            "accuracy": baseline["accuracy"],
            "macro_f1": baseline["macro_f1"],
            "per_language": baseline["per_language"],
        }

    print_report(report, baseline)

    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / "intent_metrics.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {out.relative_to(ROOT)}")
    print("\nThe Django app picks this up automatically -- LocalIntentClassifier "
          "loads INTENT_MODEL_PATH on first use and reports nlu_backend="
          "'muril_intent' instead of 'keyword_baseline'.")


if __name__ == "__main__":
    main()
