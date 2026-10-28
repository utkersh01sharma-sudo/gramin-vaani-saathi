# -*- coding: utf-8 -*-
"""OpenCV: read and check a UPI QR code; recognise a banknote.

QR
--
Decoding tries the cheap path first and only escalates on failure:
  1. cv2.QRCodeDetector on the image as taken
  2. the same after CLAHE contrast equalisation (dim shop interiors)
  3. the same after adaptive thresholding (glare, uneven light)
  4. pyzbar, which tolerates damaged and low-resolution codes better

Then three kinds of check, all of which produce *warnings*, never a silent
pass/fail, because the person holding the phone decides whether to pay:

  * the UPI URI itself -- scheme, a well-formed VPA, a pre-filled amount, an
    embedded redirect URL
  * more than one QR in the frame -- the classic sticker-over-sticker fraud at
    a shop counter leaves two codes visible from many angles
  * a tamper heuristic around the code (below)

Tamper heuristic. A fraudster's QR is printed on a sticker and pressed over the
shop's own by hand. A code printed as part of the poster shares the poster's
orientation exactly; a hand-pasted sticker is almost never square to it. So the
score is the angle between the code's module grid and the dominant orientation
of everything printed around it. The first version of this heuristic used the
sticker's edge and the brightness step at its border instead; measured on
synthetic posters those separated printed from pasted at AUC 0.79 and 0.61,
against 0.95 for rotation, because a printed code also sits on a white panel
with a hard edge. Rotation alone: AUC 0.92 overall, no false alarms, and about
half of all stickers caught -- the rest are pasted within a degree or so of
square, which a photo cannot tell from print. See ml/eval_qr_tamper.py. The UI
words a high score as "this code may have been stuck on top", never as fact.

Notes
-----
A MobileNetV3-Small trained by ml/train_notes.py on photographs of real notes.
That model needs 60-100 photos per denomination, which have to be taken by
hand. Until the artifact exists the adapter uses a colour heuristic: each note
in the Mahatma Gandhi New Series has a distinct base colour, so the note is
cropped by its largest quadrilateral, and its median hue and saturation are
matched to the nearest reference colour. The response says which backend
answered, and the heuristic's confidence is capped so the UI always says
"check it yourself" when it is the one answering.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
from django.conf import settings

from ..base import NotePrediction, QRResult, VisionAdapter

logger = logging.getLogger(__name__)

VPA_RE = re.compile(r"^[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z][a-zA-Z0-9.\-]{1,63}$")
DENOMINATIONS = [10, 20, 50, 100, 200, 500]

# Base colours of the Mahatma Gandhi New Series, as (hue 0-179, saturation 0-255)
# in OpenCV HSV. Measured from RBI reference images, then rounded; deliberately
# coarse -- this is a fallback, and the confidence it reports is capped.
NOTE_COLOURS = {
    10: (12, 120),    # chocolate brown
    20: (30, 120),    # greenish yellow
    50: (95, 110),    # fluorescent blue
    100: (130, 60),   # lavender
    200: (22, 170),   # bright yellow / orange
    500: (60, 25),    # stone grey
}
HEURISTIC_MAX_CONFIDENCE = 0.6


def _load_bgr(path: str):
    import cv2

    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("not an image")
    # Phone photos are 12 MP; the decoder needs a fraction of that, and the
    # heuristics are scale-normalised. Cap the long side for speed.
    h, w = img.shape[:2]
    scale = 1600 / max(h, w)
    if scale < 1:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return img


# ---------------------------------------------------------------------- QR
def decode_qr(img) -> list[tuple[str, np.ndarray | None]]:
    """Every QR found, as (payload, 4x2 corner points or None)."""
    import cv2

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    thresh = cv2.adaptiveThreshold(clahe, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 31, 5)
    detector = cv2.QRCodeDetector()
    for candidate in (gray, clahe, thresh):
        try:
            ok, payloads, points, _ = detector.detectAndDecodeMulti(candidate)
        except cv2.error:
            ok = False
        if ok:
            found = [(p, pts) for p, pts in zip(payloads, points) if p]
            if found:
                return found

    try:
        from pyzbar import pyzbar

        found = []
        for code in pyzbar.decode(gray):
            if code.type == "QRCODE":
                pts = np.array([[p.x, p.y] for p in code.polygon], dtype=np.float32)
                found.append((code.data.decode("utf-8", "replace"), pts if len(pts) == 4 else None))
        return found
    except Exception:  # noqa: BLE001 -- zbar DLL missing is a degraded mode, not an error
        logger.warning("pyzbar unavailable; OpenCV decoding only")
        return []


def parse_upi(payload: str) -> dict:
    parsed = urlparse(payload.strip())
    if parsed.scheme.lower() != "upi":
        return {"is_upi": False}
    q = {k.lower(): v[0] for k, v in parse_qs(parsed.query).items()}
    amount = None
    if q.get("am"):
        try:
            amount = float(q["am"])
        except ValueError:
            amount = None
    return {
        "is_upi": True,
        "action": (parsed.netloc or parsed.path).strip("/").lower(),
        "pa": q.get("pa", ""),
        "pn": q.get("pn", ""),
        "am": amount,
        "url": q.get("url", ""),
        "raw_params": q,
    }


def _dominant_angle(gx: np.ndarray, gy: np.ndarray, mask: np.ndarray) -> float:
    """Dominant edge orientation in degrees, modulo 90, weighted by gradient strength.

    Uses the 4-theta trick: multiplying the angle by four makes 0, 90, 180 and
    270 degrees the same direction, so the horizontal and vertical edges of
    text, borders and QR modules all vote for one orientation.
    """
    mag = np.hypot(gx[mask], gy[mask])
    theta = np.arctan2(gy[mask], gx[mask])
    s, c = (mag * np.sin(4 * theta)).sum(), (mag * np.cos(4 * theta)).sum()
    return float(np.degrees(np.arctan2(s, c) / 4))


def tamper_features(img, pts: np.ndarray | None) -> dict | None:
    import cv2

    if pts is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    h, w = gray.shape
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    centre = pts.mean(axis=0)
    size = float(np.linalg.norm(pts[0] - pts[2]) / np.sqrt(2))
    if size < 20:
        return None

    def mask_for(scale: float) -> np.ndarray:
        poly = (centre + (pts - centre) * scale).astype(np.int32)
        m = np.zeros((h, w), np.uint8)
        cv2.fillConvexPoly(m, poly, 1)
        return m.astype(bool)

    code = mask_for(1.0)
    near = mask_for(1.35) & ~code          # quiet zone and, if pasted, the sticker border
    far = mask_for(1.9) & ~mask_for(1.5)   # the poster around it
    if near.sum() < 50 or far.sum() < 50:
        return None

    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad = np.hypot(gx, gy)
    boundary = mask_for(1.5) & ~mask_for(1.3)

    # Rotation mismatch: the code's own module grid against the poster's text
    # and graphics. Printed together, they share an orientation to well under a
    # degree even through a tilted camera, because perspective skews both
    # alike. A sticker pressed on by hand is almost never that square.
    outside = ~mask_for(1.4)
    qr_angle = _dominant_angle(gx, gy, code)
    poster_angle = _dominant_angle(gx, gy, outside)
    mismatch = abs(qr_angle - poster_angle) % 90
    mismatch = min(mismatch, 90 - mismatch)

    return {
        "rotation_mismatch_deg": round(mismatch, 2),
        # A sticker's edge is a hard step all the way round.
        "edge_ratio": round(float(grad[boundary].mean() / (grad[far].mean() + 1.0)), 3),
        # Brightness step between the margin and the poster.
        "brightness_step": round(float(abs(gray[near].mean() - gray[far].mean()) / 255.0), 3),
    }


# Degrees of rotation mismatch at which the score saturates. Chosen from the
# physics, not fitted: below ~0.7 degrees the measurement is inside the noise of
# a printed poster photographed at an angle; a hand-pressed sticker is usually
# several degrees off.
ROTATION_FLOOR_DEG = 0.7
ROTATION_FULL_DEG = 2.5


def tamper_score(img, pts: np.ndarray | None) -> float:
    """0..1: how likely the code is a sticker pasted over the poster.

    Rotation mismatch carries the decision. The edge and brightness cues from
    the first version of this heuristic are still computed and returned by
    tamper_features() for the report, but measured on synthetic posters they
    barely separated the classes (AUC 0.65, see ml/reports/qr_tamper.json): a
    printed code also sits on a white panel with a hard edge. They no longer
    contribute to the score.
    """
    f = tamper_features(img, pts)
    if f is None:
        return 0.0
    span = ROTATION_FULL_DEG - ROTATION_FLOOR_DEG
    return float(round(min(max((f["rotation_mismatch_deg"] - ROTATION_FLOOR_DEG) / span, 0.0), 1.0), 3))


# ---------------------------------------------------------------------- notes
def crop_note(img):
    """Largest 4-sided contour, perspective-corrected. Falls back to the whole frame."""
    import cv2

    gray = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    edges = cv2.dilate(cv2.Canny(gray, 40, 120), None, iterations=2)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area = img.shape[0] * img.shape[1]
    for c in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        if cv2.contourArea(c) < 0.15 * area:
            break
        approx = cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)
        if len(approx) == 4:
            src = approx.reshape(4, 2).astype(np.float32)
            s, d = src.sum(1), np.diff(src, axis=1).ravel()
            ordered = np.array([src[s.argmin()], src[d.argmin()], src[s.argmax()], src[d.argmax()]])
            dst = np.array([[0, 0], [400, 0], [400, 180], [0, 180]], dtype=np.float32)
            return cv2.warpPerspective(img, cv2.getPerspectiveTransform(ordered, dst), (400, 180)), True
    return img, False


def colour_guess(note_bgr) -> tuple[int | None, float]:
    import cv2

    hsv = cv2.cvtColor(note_bgr, cv2.COLOR_BGR2HSV)
    hue, sat, val = (np.median(hsv[..., i]) for i in range(3))
    if val < 40:
        return None, 0.0
    best, best_d, second_d = None, 1e9, 1e9
    for denom, (h_ref, s_ref) in NOTE_COLOURS.items():
        dh = min(abs(hue - h_ref), 180 - abs(hue - h_ref)) / 90.0   # hue is circular
        ds = abs(sat - s_ref) / 255.0
        d = np.hypot(dh * 1.5, ds)
        if d < best_d:
            best, best_d, second_d = denom, d, best_d
        elif d < second_d:
            second_d = d
    margin = (second_d - best_d) / (second_d + 1e-6)
    return best, float(min(HEURISTIC_MAX_CONFIDENCE, 0.25 + margin))


class LocalVision(VisionAdapter):
    def __init__(self):
        self.note_dir = Path(settings.NOTE_MODEL_PATH)
        self._lock = threading.Lock()
        self._note_model = None
        self._note_labels = None
        self._note_loaded = False

    @property
    def note_backend(self) -> str:
        self._load_note_model()
        return "notenet" if self._note_model is not None else "colour_heuristic"

    # ------------------------------------------------------------- QR
    def read_qr(self, image_path: str) -> QRResult:
        img = _load_bgr(image_path)
        codes = decode_qr(img)
        if not codes:
            return QRResult(warnings=["no_qr_found"])

        payload, pts = codes[0]
        result = QRResult(raw=payload)
        if len(codes) > 1:
            result.warnings.append("multiple_qr")

        upi = parse_upi(payload)
        if not upi["is_upi"]:
            result.warnings.append("not_upi")
            if payload.lower().startswith(("http://", "https://")):
                result.warnings.append("is_web_link")
            return result

        result.payee_vpa = upi["pa"]
        result.payee_name = upi["pn"]
        result.amount = upi["am"]
        result.is_valid_upi = upi["action"] == "pay" and bool(VPA_RE.match(upi["pa"] or ""))
        if not result.is_valid_upi:
            result.warnings.append("malformed_upi")
        if upi["am"] is not None:
            result.warnings.append("amount_prefilled")
        if upi["url"]:
            result.warnings.append("embedded_url")

        result.tamper_score = tamper_score(img, pts)
        if result.tamper_score >= 0.5:
            result.warnings.append("possible_sticker")
        return result

    # ------------------------------------------------------------- notes
    def _load_note_model(self) -> None:
        if self._note_loaded:
            return
        with self._lock:
            if self._note_loaded:
                return
            weights, labels = self.note_dir / "model.pt", self.note_dir / "labels.json"
            if weights.exists() and labels.exists():
                try:
                    import torch
                    from torchvision.models import mobilenet_v3_small

                    self._note_labels = json.loads(labels.read_text(encoding="utf-8"))
                    model = mobilenet_v3_small(num_classes=len(self._note_labels))
                    model.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True))
                    self._note_model = model.eval()
                    logger.info("NoteNet loaded from %s", self.note_dir)
                except Exception:  # noqa: BLE001
                    logger.exception("NoteNet failed to load; colour heuristic")
            self._note_loaded = True

    def identify_note(self, image_path: str) -> NotePrediction:
        img = _load_bgr(image_path)
        note, found = crop_note(img)
        self._load_note_model()

        if self._note_model is not None:
            import cv2
            import torch

            rgb = cv2.cvtColor(cv2.resize(note, (224, 224)), cv2.COLOR_BGR2RGB).astype(np.float32) / 255
            rgb = (rgb - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
            x = torch.from_numpy(rgb.transpose(2, 0, 1)).float().unsqueeze(0)
            with torch.no_grad():
                probs = torch.softmax(self._note_model(x), dim=-1)[0].numpy()
            label = self._note_labels[int(probs.argmax())]
            conf = float(probs.max())
            if label == "not_a_note":
                return NotePrediction(denomination=None, confidence=conf, is_note=False)
            return NotePrediction(denomination=int(label), confidence=conf)

        denom, conf = colour_guess(note)
        if not found:
            conf *= 0.7    # no clear note outline: the colour may be the table
        return NotePrediction(denomination=denom, confidence=round(conf, 3), is_note=denom is not None)
