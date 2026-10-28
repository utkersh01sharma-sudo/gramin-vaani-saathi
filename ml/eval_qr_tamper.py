# -*- coding: utf-8 -*-
"""Evaluate the QR pipeline on synthetic shop posters, and write demo samples.

    python ml/eval_qr_tamper.py

Each poster is a shop's UPI QR printed on a white panel, on a coloured,
textured standee, photographed with a lighting gradient, sensor noise, blur and
a slight perspective tilt. Half of them then get a fraudster's sticker pasted
over the code: a different VPA, its own white border in a slightly different
white, a few degrees of rotation, and a drop shadow. In a third of the tampered
posters the sticker is offset enough that the shop's original code is still
partly decodable beside it.

What this measures and what it does not. It measures whether the heuristic
separates "printed" from "pasted" under the variations modelled here, and
whether decoding survives the photo degradations. It does not measure real
shop counters -- the generator and the heuristic were written by the same
person, so a high number here is necessary, not sufficient. The report says so.

Writes ml/reports/qr_tamper.json and docs/samples/qr_*.png.
"""
from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import cv2  # noqa: E402
import django  # noqa: E402

django.setup()

from ai.local.vision import decode_qr, parse_upi, tamper_features, tamper_score  # noqa: E402

SHOP = "upi://pay?pa=ramkirana@sandbox&pn=Ram%20Kirana%20Store&cu=INR"
FRAUD = "upi://pay?pa=quickcash77@okfraud&pn=Ram%20Kirana%20Store&cu=INR"
REDIRECT = "upi://pay?pa=ramkirana@sandbox&pn=Ram%20Kirana%20Store&am=4999&url=http://kyc-verify.top/pay"
SAMPLES = ROOT / "docs" / "samples"
N_PER_CLASS = 60
SEED = 11


def qr_image(payload: str, box: int = 8) -> np.ndarray:
    import qrcode

    q = qrcode.QRCode(border=2, box_size=box, error_correction=qrcode.constants.ERROR_CORRECT_M)
    q.add_data(payload)
    q.make(fit=True)
    img = np.array(q.make_image(fill_color="black", back_color="white").convert("RGB"))
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


def poster(rng: random.Random, payload: str = SHOP) -> tuple[np.ndarray, tuple[int, int, int]]:
    h, w = 900, 700
    base = np.array([rng.randint(30, 220) for _ in range(3)], dtype=np.float32)
    img = np.ones((h, w, 3), np.float32) * base
    img += np.random.normal(0, rng.uniform(4, 14), img.shape)          # print texture
    for _ in range(rng.randint(3, 8)):                                  # text blocks, logos
        x, y = rng.randint(0, w - 120), rng.randint(0, h - 40)
        cv2.rectangle(img, (x, y), (x + rng.randint(60, 300), y + rng.randint(10, 40)),
                      [rng.randint(0, 255) for _ in range(3)], -1)
    code = qr_image(payload)
    size = code.shape[0]
    panel = int(size * rng.uniform(1.25, 1.9))
    cx, cy = w // 2 + rng.randint(-60, 60), h // 2 + rng.randint(-60, 60)
    white = rng.randint(235, 252)
    cv2.rectangle(img, (cx - panel // 2, cy - panel // 2), (cx + panel // 2, cy + panel // 2),
                  (white, white, white), -1)
    img[cy - size // 2: cy - size // 2 + size, cx - size // 2: cx - size // 2 + size] = code
    return np.clip(img, 0, 255).astype(np.uint8), (cx, cy, size)


def paste_sticker(img: np.ndarray, rng: random.Random, centre, offset: bool,
                  angle: float | None = None) -> np.ndarray:
    cx, cy, size = centre
    code = qr_image(FRAUD, box=rng.choice([7, 8, 9]))
    border = int(code.shape[0] * rng.uniform(0.08, 0.2))
    tint = rng.randint(225, 255)
    sticker = cv2.copyMakeBorder(code, border, border, border, border, cv2.BORDER_CONSTANT,
                                 value=(tint, tint - rng.randint(0, 8), tint - rng.randint(0, 12)))
    angle = rng.uniform(-6, 6) if angle is None else angle
    sh = sticker.shape[0]
    m = cv2.getRotationMatrix2D((sh / 2, sh / 2), angle, 1.0)
    rotated = cv2.warpAffine(sticker, m, (sh, sh), borderValue=(0, 0, 0))
    mask = cv2.warpAffine(np.ones((sh, sh), np.uint8) * 255, m, (sh, sh))
    dx = rng.randint(int(size * 0.55), int(size * 0.8)) * rng.choice([-1, 1]) if offset else rng.randint(-8, 8)
    dy = rng.randint(-8, 8)
    x0, y0 = cx - sh // 2 + dx, cy - sh // 2 + dy
    out = img.copy()
    # Drop shadow first, then the sticker.
    shadow = cv2.GaussianBlur(mask, (21, 21), 0).astype(np.float32) / 255 * 0.35
    for (ox, oy, layer, alpha) in ((5, 6, None, shadow), (0, 0, rotated, mask.astype(np.float32) / 255)):
        ys, xs = slice(max(y0 + oy, 0), min(y0 + oy + sh, out.shape[0])), slice(max(x0 + ox, 0), min(x0 + ox + sh, out.shape[1]))
        a = alpha[ys.start - (y0 + oy): ys.stop - (y0 + oy), xs.start - (x0 + ox): xs.stop - (x0 + ox)][..., None]
        region = out[ys, xs].astype(np.float32)
        top = np.zeros_like(region) if layer is None else \
            layer[ys.start - (y0 + oy): ys.stop - (y0 + oy), xs.start - (x0 + ox): xs.stop - (x0 + ox)].astype(np.float32)
        out[ys, xs] = (region * (1 - a) + top * a).astype(np.uint8)
    return out


def photograph(img: np.ndarray, rng: random.Random) -> np.ndarray:
    h, w = img.shape[:2]
    grad = np.linspace(rng.uniform(0.7, 1.0), rng.uniform(0.9, 1.15), w)[None, :, None]
    out = np.clip(img.astype(np.float32) * grad + np.random.normal(0, 4, img.shape), 0, 255).astype(np.uint8)
    d = rng.uniform(0, 0.05) * w
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([[d, rng.uniform(0, d)], [w - rng.uniform(0, d), 0], [w, h], [rng.uniform(0, d), h - rng.uniform(0, d)]])
    out = cv2.warpPerspective(out, cv2.getPerspectiveTransform(src, dst), (w, h), borderMode=cv2.BORDER_REPLICATE)
    return cv2.GaussianBlur(out, (3, 3), rng.uniform(0.1, 1.0))


def auc(pos: list[float], neg: list[float]) -> float:
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def main() -> None:
    rng = random.Random(SEED)
    np.random.seed(SEED)
    rows = []
    for i in range(N_PER_CLASS * 2):
        tampered = i >= N_PER_CLASS
        offset = tampered and (i % 3 == 0)
        img, centre = poster(rng)
        if tampered:
            img = paste_sticker(img, rng, centre, offset)
        img = photograph(img, rng)
        codes = decode_qr(img)
        decoded = [parse_upi(p).get("pa", "") for p, _ in codes]
        primary = codes[0] if codes else (None, None)
        rows.append({
            "tampered": tampered, "offset": offset, "n_codes": len(codes), "decoded": decoded,
            "tamper_score": tamper_score(img, primary[1]) if codes else None,
            "features": tamper_features(img, primary[1]) if codes else None,
        })

    clean = [r for r in rows if not r["tampered"]]
    bad = [r for r in rows if r["tampered"]]
    decode_rate = sum(r["n_codes"] > 0 for r in rows) / len(rows)
    pos = [r["tamper_score"] for r in bad if r["tamper_score"] is not None]
    neg = [r["tamper_score"] for r in clean if r["tamper_score"] is not None]
    flagged = lambda r: (r["tamper_score"] or 0) >= 0.5 or r["n_codes"] > 1  # noqa: E731
    tp = sum(flagged(r) for r in bad)
    fp = sum(flagged(r) for r in clean)
    # Each cue on its own, to show which one carries the signal.
    feature_auc = {}
    for name in ("rotation_mismatch_deg", "edge_ratio", "brightness_step"):
        fp_ = [r["features"][name] for r in bad if r["features"]]
        fn_ = [r["features"][name] for r in clean if r["features"]]
        feature_auc[name] = round(auc(fp_, fn_), 4)
    report = {
        "n_posters": len(rows), "decode_rate": round(decode_rate, 4),
        "feature_auc": feature_auc,
        "tamper_auc": round(auc(pos, neg), 4),
        "mean_score_clean": round(float(np.mean(neg)), 4), "mean_score_tampered": round(float(np.mean(pos)), 4),
        "detection_rate": round(tp / len(bad), 4), "false_alarm_rate": round(fp / len(clean), 4),
        "multiple_qr_seen_when_offset": round(
            sum(r["n_codes"] > 1 for r in bad if r["offset"]) / max(1, sum(r["offset"] for r in bad)), 4),
        "fraud_vpa_decoded_when_tampered": round(
            sum("quickcash77@okfraud" in r["decoded"] for r in bad) / len(bad), 4),
        "caveat": "Synthetic posters from a generator written alongside the heuristic. "
                  "Necessary evidence, not sufficient: real shop photos are needed for a field number.",
    }
    print(json.dumps(report, indent=2))
    (ROOT / "ml" / "reports" / "qr_tamper.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Demo samples: one of each case, at a size a phone camera or upload will read.
    SAMPLES.mkdir(parents=True, exist_ok=True)
    demo = random.Random(3)
    img, centre = poster(demo)
    cv2.imwrite(str(SAMPLES / "qr_shop_genuine.png"), photograph(img, demo))
    cv2.imwrite(str(SAMPLES / "qr_sticker_tampered.png"), photograph(paste_sticker(img, demo, centre, offset=False, angle=4.5), demo))
    img, _ = poster(demo, REDIRECT)
    cv2.imwrite(str(SAMPLES / "qr_redirect_prefilled.png"), photograph(img, demo))
    print(f"wrote demo samples to {SAMPLES.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
