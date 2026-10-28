# -*- coding: utf-8 -*-
"""Train NoteNet: MobileNetV3-Small on photographs of Indian banknotes.

This needs photographs that only a person with the notes can take. Lay them out:

    ml/data/notes/train/10/*.jpg    ml/data/notes/test/10/*.jpg
    ml/data/notes/train/20/*.jpg    ml/data/notes/test/20/*.jpg
    ...                             ...
    ml/data/notes/train/500/*.jpg   ml/data/notes/test/500/*.jpg
    ml/data/notes/train/not_a_note/ ml/data/notes/test/not_a_note/

60-100 photos per class in train: front and back, folded and flat, worn and
new, on different surfaces, in daylight and under a tube light. The **test**
folder must be photographed in a different session -- another room, another
day, other lighting. A random split of one session's photos puts near-identical
frames on both sides and reports 99% for a model that has learned the table.

    python ml/train_notes.py               # fine-tune head, then unfreeze, evaluate
    python ml/train_notes.py --epochs 15

Writes ml/artifacts/notes/{model.pt,labels.json} -- which the API picks up in
place of the colour heuristic automatically -- and ml/reports/note_metrics.json.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "ml" / "data" / "notes"
ARTIFACTS = ROOT / "ml" / "artifacts" / "notes"
REPORTS = ROOT / "ml" / "reports"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--head-epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=3e-4)
    args = ap.parse_args()

    if not (DATA / "train").exists() or not (DATA / "test").exists():
        raise SystemExit(
            f"No photographs at {DATA}/train and {DATA}/test.\n"
            "NoteNet needs real photos of real notes; see the docstring at the top of this file.\n"
            "Until they exist the API answers with its colour heuristic and says so."
        )

    import numpy as np
    import torch
    from sklearn.metrics import confusion_matrix
    from torch import nn
    from torch.utils.data import DataLoader
    from torchvision import datasets, transforms
    from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

    norm = transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    # Heavy augmentation stands in for the variety 60 photos cannot cover:
    # angle, lighting, blur, folds (approximated by perspective), occlusion.
    train_tf = transforms.Compose([
        transforms.RandomResizedCrop(224, scale=(0.6, 1.0), ratio=(1.6, 2.6)),
        transforms.RandomPerspective(0.3, p=0.5),
        transforms.RandomRotation(15),
        transforms.ColorJitter(0.4, 0.4, 0.3, 0.03),
        transforms.RandomApply([transforms.GaussianBlur(5)], p=0.3),
        transforms.ToTensor(), norm,
        transforms.RandomErasing(p=0.3, scale=(0.02, 0.15)),
    ])
    test_tf = transforms.Compose([transforms.Resize((224, 224)), transforms.ToTensor(), norm])
    train_ds = datasets.ImageFolder(DATA / "train", train_tf)
    test_ds = datasets.ImageFolder(DATA / "test", test_tf)
    labels = train_ds.classes
    print(f"classes {labels} | train {len(train_ds)} | test {len(test_ds)}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.IMAGENET1K_V1)
    model.classifier[3] = nn.Linear(model.classifier[3].in_features, len(labels))
    model.to(device)
    train_dl = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=0)
    test_dl = DataLoader(test_ds, batch_size=64, num_workers=0)
    loss_fn = nn.CrossEntropyLoss(label_smoothing=0.05)

    def run(epochs: int, train_backbone: bool, lr: float) -> None:
        for p in model.features.parameters():
            p.requires_grad = train_backbone
        opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs * len(train_dl))
        for epoch in range(epochs):
            model.train()
            total = 0.0
            for x, y in train_dl:
                x, y = x.to(device), y.to(device)
                opt.zero_grad()
                loss = loss_fn(model(x), y)
                loss.backward()
                opt.step()
                sched.step()
                total += loss.item() * len(y)
            print(f"  {'full' if train_backbone else 'head'} epoch {epoch + 1}/{epochs} "
                  f"loss {total / len(train_ds):.4f}")

    started = time.time()
    run(args.head_epochs, train_backbone=False, lr=args.lr * 3)   # new head first
    run(args.epochs, train_backbone=True, lr=args.lr)             # then everything
    minutes = (time.time() - started) / 60

    model.eval()
    gold, pred = [], []
    with torch.no_grad():
        for x, y in test_dl:
            pred += model(x.to(device)).argmax(1).cpu().tolist()
            gold += y.tolist()
    gold, pred = np.array(gold), np.array(pred)
    acc = float((gold == pred).mean())
    per_class = {labels[i]: round(float((pred[gold == i] == i).mean()), 4) for i in range(len(labels))
                 if (gold == i).any()}
    print(f"\ntest accuracy {acc:.4f} (separate photo session) | per class {per_class}")

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    torch.save(model.cpu().state_dict(), ARTIFACTS / "model.pt")
    (ARTIFACTS / "labels.json").write_text(json.dumps(labels), encoding="utf-8")
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "note_metrics.json").write_text(json.dumps({
        "model": "notenet_mobilenet_v3_small", "classes": labels, "n_train": len(train_ds),
        "n_test": len(test_ds), "accuracy": round(acc, 4), "per_class_accuracy": per_class,
        "confusion_matrix": confusion_matrix(gold, pred).tolist(), "train_minutes": round(minutes, 2),
    }, indent=2), encoding="utf-8")
    print(f"saved {ARTIFACTS}")


if __name__ == "__main__":
    main()
