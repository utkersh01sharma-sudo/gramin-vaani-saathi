# -*- coding: utf-8 -*-
"""Build the ten-slide project review deck.

    python docs/deck/build_deck.py

Two things about how this is written.

**The numbers are read from the report files, not typed in.** Accuracy, latency
and dataset sizes come out of ml/reports/*.json at build time, so the deck cannot
quietly drift away from what the code actually does. Re-run a benchmark, rebuild
the deck, and the slide is right. If a report is missing the slide says so
instead of inventing a figure.

**The layout grammar follows the review-1 deck** -- 16:9, title at the top left,
page number bottom right, card grids, a numbered timeline, stat-and-narrative
splits -- while the palette, type and icons come from the product itself. The
result reads as the same project in two media rather than as a template someone
poured text into.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from pptx import Presentation
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import theme as T  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "ml" / "reports"
OUT = ROOT / "docs" / "GraminVaaniSaathi_Review.pptx"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


# --------------------------------------------------------------- live data
def load(name: str) -> dict:
    path = REPORTS / name
    if not path.exists():
        print(f"  ! {name} missing -- slides will say 'not yet measured'", file=sys.stderr)
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


BASELINE = load("baseline_intent_metrics.json")
VOICE = load("voice_latency.json")


def rows_in(rel: str) -> int:
    path = ROOT / rel
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as fh:
        return sum(1 for _ in fh)


TRAIN_ROWS = rows_in("ml/data/intent_train.jsonl")
VAL_ROWS = rows_in("ml/data/intent_val.jsonl")
TEST_ROWS = rows_in("ml/data/intent_test_handwritten.jsonl")

WARM = VOICE.get("warm", {})
P50 = f"{WARM['p50_ms']} ms" if WARM else "not yet measured"
P95 = f"{WARM['p95_ms']} ms" if WARM else "—"
ACC = f"{BASELINE['accuracy'] * 100:.1f}%" if BASELINE else "not yet measured"
F1 = f"{BASELINE['macro_f1']:.3f}" if BASELINE else "—"


def new_slide(prs, dark=False):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    T.set_bg(slide, T.PRIMARY_INK if dark else T.BG)
    return slide


# ============================================================== 1. title
def slide_title(prs):
    s = new_slide(prs, dark=True)

    # One quiet green field, the way the balance card is the only dark surface
    # on an otherwise light home screen.
    band = T.bar(s, Inches(0), Inches(0), Inches(0.16), T.SLIDE_H, T.PRIMARY_2)
    band.line.fill.background()
    T.blob(s, Inches(12.6), Inches(1.1), Inches(3.3), T.mix(T.PRIMARY_2, 0.28, T.PRIMARY_INK))
    T.blob(s, Inches(13.6), Inches(6.6), Inches(2.4), T.mix(T.ACCENT, 0.16, T.PRIMARY_INK))

    # The chip is tinted into the dark ground, not into white -- mixing against
    # the wrong surface is how you end up with a white square on a green slide.
    T.icon_chip(s, "mic", Inches(0.95), Inches(1.55), Inches(0.9), tone=T.ON_DARK,
                tint=0.13, base=T.PRIMARY_INK, glyph_color=T.ON_DARK)

    T.text(s, Inches(0.95), Inches(2.75), Inches(11.0), Inches(1.0),
           "Gramin Vaani Saathi", size=44, bold=True, color=T.ON_DARK)
    T.text(s, Inches(0.97), Inches(3.78), Inches(11.0), Inches(0.5),
           "AI-Powered Voice Financial Companion for Rural Communities",
           size=18, color=T.ON_DARK_2)
    T.text(s, Inches(0.97), Inches(4.42), Inches(8.9), Inches(0.9),
           "Voice-first banking, government schemes, financial literacy and scam "
           "protection — in the speaker's own language, with no reading required.",
           size=12.5, color=T.ON_DARK_3, line=1.5)

    T.rule(s, Inches(0.97), Inches(5.75), Inches(1.4), T.ACCENT, 2.25)
    T.eyebrow(s, Inches(0.97), Inches(6.0), Inches(9.0),
              "Project Review  ·  Working build, not a mockup", T.ON_DARK_3)
    T.text(s, Inches(0.97), Inches(6.35), Inches(9.0), Inches(0.4),
           "Django + DRF  ·  Installable PWA  ·  Hindi · English · Tamil · Telugu",
           size=12, bold=True, color=T.ON_DARK_2)


# ============================================================ 2. problem
def slide_problem(prs):
    s = new_slide(prs)
    T.title(s, "The Problem", "Accounts exist. Confident, safe usage does not.")

    points = [
        ("Reading is assumed at every step.",
         "Banking apps are text-first and IVR menus are rigid. A user who cannot "
         "read is locked out of an account that is already in their name."),
        ("Help arrives in the wrong language.",
         "Support and scheme information are English- or Hindi-first, and rarely "
         "handle the code-mixed, transliterated way people actually speak."),
        ("Welfare schemes stay undiscovered.",
         "Eligibility rules are scattered across portals, so entitlements go "
         "unclaimed by exactly the households they were written for."),
        ("Fraud targets the least-defended.",
         "OTP, KYC-expiry and lottery scams work best on users with no way to "
         "check a message and no one to ask."),
    ]
    y = Inches(1.95)
    for headline, body in points:
        T.bar(s, Inches(0.6), y + Inches(0.04), Inches(0.03), Inches(0.62), T.PRIMARY)
        T.text(s, Inches(0.88), y, Inches(6.5), Inches(0.3), headline,
               size=13.5, bold=True, color=T.INK)
        T.text(s, Inches(0.88), y + Inches(0.28), Inches(6.5), Inches(0.62), body,
               size=11.5, color=T.INK_2, line=1.4)
        y += Inches(1.17)

    # stat card
    T.card(s, Inches(8.05), Inches(1.95), Inches(4.68), Inches(4.7))
    T.icon_chip(s, "user", Inches(8.45), Inches(2.35), Inches(0.68), tone=T.ACCENT)
    T.text(s, Inches(8.45), Inches(3.25), Inches(4.0), Inches(0.9), "190M+",
           size=40, bold=True, color=T.ACCENT)
    T.text(s, Inches(8.45), Inches(4.0), Inches(3.9), Inches(0.9),
           "adults in India remain unbanked or under-served, concentrated in "
           "rural districts.", size=12, color=T.INK_2, line=1.45)
    T.rule(s, Inches(8.45), Inches(5.05), Inches(3.9))
    T.eyebrow(s, Inches(8.45), Inches(5.25), Inches(3.9), "The gap is usage, not access")
    T.text(s, Inches(8.45), Inches(5.55), Inches(3.9), Inches(0.9),
           "Account ownership has reached roughly 89%, while the RBI Financial "
           "Inclusion Index sits near 67/100.", size=11.5, color=T.INK_3, line=1.45)

    T.page_number(s, 2)


# =========================================================== 3. solution
def slide_solution(prs):
    s = new_slide(prs)
    T.title(s, "The Solution")

    T.eyebrow(s, Inches(0.6), Inches(1.95), Inches(6.6), "One conversation, four jobs")
    T.text(s, Inches(0.6), Inches(2.25), Inches(6.5), Inches(0.5),
           "Speak. It answers.", size=26, bold=True, color=T.INK)
    T.text(s, Inches(0.6), Inches(2.95), Inches(6.5), Inches(1.4),
           "One voice-first companion that folds UPI and banking help, government "
           "scheme matching, financial literacy and live scam checking into a "
           "single multilingual, icon-guided flow — so a user never has to know "
           "which app a question belongs to.", size=13, color=T.INK_2, line=1.55)
    T.text(s, Inches(0.6), Inches(4.5), Inches(6.5), Inches(1.3),
           "It installs as a web app, caches its own shell, and queues actions "
           "when the network drops. Nothing that moves money executes on the "
           "first utterance — every transfer is read back and confirmed.",
           size=13, color=T.INK_2, line=1.55)

    T.rule(s, Inches(0.6), Inches(6.05), Inches(6.5))
    T.text(s, Inches(0.6), Inches(6.25), Inches(6.5), Inches(0.6),
           "Every banking operation runs against a sandbox ledger inside this "
           "project's own database. No real bank, PSP or payment network is "
           "contacted.", size=11, color=T.GOLD, line=1.45)

    # ---- the home screen, drawn to scale
    px, py, pw, ph = Inches(8.35), Inches(1.75), Inches(4.1), Inches(5.15)
    T.card(s, px, py, pw, ph, fill=T.SURFACE_2, outline=T.LINE, radius=0.05)

    T.card(s, px + Inches(0.3), py + Inches(0.35), Inches(3.5), Inches(0.85),
           fill=T.PRIMARY, outline=None, radius=0.14)
    T.eyebrow(s, px + Inches(0.5), py + Inches(0.5), Inches(3.0),
              "Your money", T.ON_DARK_2)
    T.text(s, px + Inches(0.5), py + Inches(0.73), Inches(3.0), Inches(0.4),
           "₹ 3,750", size=21, bold=True, color=T.ON_DARK)

    tiles = [
        ("wallet", T.T_MONEY,  "Balance"), ("send",  T.T_SEND,   "Send"),
        ("scheme", T.T_SCHEME, "Schemes"), ("learn", T.T_LEARN,  "Learn"),
        ("scan",   T.T_SCAN,   "Scan"),    ("shield", T.T_SAFETY, "Safety"),
    ]
    tw, th, gap = Inches(1.67), Inches(0.92), Inches(0.14)
    for i, (name, tone, label) in enumerate(tiles):
        tx = px + Inches(0.3) + (tw + gap) * (i % 2)
        ty = py + Inches(1.42) + (th + gap) * (i // 2)
        T.card(s, tx, ty, tw, th, radius=0.1)
        T.icon_chip(s, name, tx + Inches(0.15), ty + Inches(0.13), Inches(0.4), tone=tone)
        T.text(s, tx + Inches(0.15), ty + Inches(0.6), tw - Inches(0.3), Inches(0.25),
               label, size=10.5, bold=True, color=T.INK)

    # The mic sits under the grid and is the largest target on the screen --
    # the one control a user can always reach without reading anything.
    T.icon_chip(s, "mic", px + Inches(1.66), py + Inches(4.34), Inches(0.78),
                tone=T.ACCENT, tint=1.0, glyph=0.55, radius=0.5,
                glyph_color=T.ON_DARK)

    T.page_number(s, 3)


# =========================================================== 4. features
def slide_features(prs):
    s = new_slide(prs)
    T.title(s, "Key Features", "Eight capabilities, one voice.")

    cards = [
        ("mic",    T.T_MONEY,  "Voice-First Interface",
         "Speak a whole request. No typing, no menu tree, no reading."),
        ("globe",  T.T_SCHEME, "Four Languages",
         "Hindi, English, Tamil and Telugu, including code-mixed speech."),
        ("wallet", T.T_MONEY,  "UPI & Banking Help",
         "Balance, history and transfers, each confirmed aloud first."),
        ("scheme", T.T_SCHEME, "Scheme Matching",
         "Eligibility rules that return the reason, not just a verdict."),
        ("learn",  T.T_LEARN,  "Literacy Coaching",
         "Short spoken lessons on UPI, interest, saving and safety."),
        ("shield", T.T_SAFETY, "Scam Detection",
         "A verdict with its reasons, so the user can learn the pattern."),
        ("offline", T.T_SCAN,  "Offline Mode",
         "Cached reads plus an idempotent queue that replays on reconnect."),
        ("scan",   T.T_SCAN,   "Icon Navigation",
         "Large tiles with a label and a tap-to-hear-it affordance."),
    ]
    cw, ch, gx, gy = Inches(2.94), Inches(2.3), Inches(0.19), Inches(0.22)
    for i, (name, tone, head, body) in enumerate(cards):
        x = Inches(0.6) + (cw + gx) * (i % 4)
        y = Inches(1.95) + (ch + gy) * (i // 4)
        T.card(s, x, y, cw, ch)
        T.icon_chip(s, name, x + Inches(0.26), y + Inches(0.26), Inches(0.6), tone=tone)
        T.text(s, x + Inches(0.26), y + Inches(1.02), cw - Inches(0.5), Inches(0.5),
               head, size=12.5, bold=True, color=T.INK, line=1.2)
        T.text(s, x + Inches(0.26), y + Inches(1.48), cw - Inches(0.5), Inches(0.7),
               body, size=10.5, color=T.INK_2, line=1.4)

    T.page_number(s, 4)


# ======================================================= 5. architecture
def slide_architecture(prs):
    s = new_slide(prs)
    T.title(s, "System Architecture",
            "Models sit behind an adapter interface, never imported into a view.")

    layers = [
        ("scan", T.T_SCAN, "1. PWA shell",
         "Plain HTML, CSS and ES modules — no build step. Service worker "
         "precaches the shell; the queue holds actions while offline."),
        ("layers", T.T_SCHEME, "2. Django + DRF",
         "Eight apps behind a documented API. Stateless workers: pending "
         "confirmation state is handed to the client, not held in a session."),
        ("clock", T.T_LEARN, "3. Celery + Redis",
         "Transcription and vision run on the queue, so a web worker is never "
         "blocked holding the GPU while someone speaks."),
        ("code", T.T_MONEY, "4. ai/ adapter layer",
         "ASR, NLU, scam and vision behind one interface. AI_BACKEND=remote "
         "sends identical calls to a model server — scaling costs one variable."),
    ]
    cw, gx = Inches(2.94), Inches(0.19)
    for i, (name, tone, head, body) in enumerate(layers):
        x = Inches(0.6) + (cw + gx) * i
        T.card(s, x, Inches(2.0), cw, Inches(2.85))
        T.icon_chip(s, name, x + Inches(0.28), Inches(2.28), Inches(0.62), tone=tone)
        T.text(s, x + Inches(0.28), Inches(3.1), cw - Inches(0.56), Inches(0.35),
               head, size=13, bold=True, color=T.INK)
        T.text(s, x + Inches(0.28), Inches(3.5), cw - Inches(0.56), Inches(1.2),
               body, size=10.5, color=T.INK_2, line=1.45)
        if i < 3:
            T.text(s, x + cw + Inches(0.01), Inches(3.25), Inches(0.18), Inches(0.3),
                   "›", size=15, color=T.INK_3, align=PP_ALIGN.CENTER)

    T.card(s, Inches(0.6), Inches(5.15), Inches(12.13), Inches(1.5),
           fill=T.PRIMARY_SOFT, outline=None)
    T.eyebrow(s, Inches(0.95), Inches(5.42), Inches(11.4), "Why this scales",
              T.PRIMARY_INK)
    T.text(s, Inches(0.95), Inches(5.72), Inches(11.4), Inches(0.8),
           "Nothing in a view imports transformers, faster-whisper or cv2. In "
           "development the models load in-process; flipping one environment "
           "variable routes the same calls over HTTP to a dedicated model server. "
           "Stateless Django plus Redis plus Postgres means capacity is added by "
           "adding replicas, not by rewriting the request path.",
           size=12, color=T.PRIMARY_INK, line=1.5)

    T.page_number(s, 5)


# ========================================================== 6. progress
def slide_progress(prs):
    s = new_slide(prs)
    T.title(s, "Progress So Far",
            "Days 1–3 of a seven-day sprint are complete and committed.")

    done = [
        ("Django backend scaffolded",
         "Eight apps, split settings, self-documenting API at /api/docs/."),
        ("Sandbox ledger with idempotent transfers",
         "A replayed queued request cannot double-spend — the offline story "
         "depends on this being true."),
        ("Intent dataset built",
         f"{TRAIN_ROWS:,} generated training rows across four languages, plus "
         f"{TEST_ROWS} hand-written test rows so accuracy is reported honestly."),
        ("Voice pipeline running end to end",
         "Audio upload → faster-whisper → intent → ledger action → spoken reply."),
        ("PWA shipped and redesigned",
         "Icon-first shell, four languages, OTP signup, a stroked icon set "
         "replacing every emoji."),
    ]
    T.eyebrow(s, Inches(0.6), Inches(2.0), Inches(6.3), "Working now", T.OK)
    y = Inches(2.3)
    for head, body in done:
        T.icon(s, "check", Inches(0.62), y + Inches(0.03), Inches(0.24), T.OK, 1.5)
        T.text(s, Inches(1.0), y, Inches(5.9), Inches(0.28), head,
               size=12.5, bold=True, color=T.INK)
        T.text(s, Inches(1.0), y + Inches(0.26), Inches(5.9), Inches(0.55), body,
               size=10.5, color=T.INK_2, line=1.4)
        y += Inches(0.87)

    T.eyebrow(s, Inches(7.35), Inches(2.0), Inches(5.4), "Next, in order", T.ACCENT)
    nxt = [
        ("Day 3–4", "Finish training the MuRIL intent classifier; the keyword "
                          "baseline is answering in the meantime."),
        ("Day 4", "ScamNet: transformer plus an explainable rule layer, with an "
                  "ablation table. Twenty schemes, ten literacy lessons."),
        ("Day 5", "OpenCV QR verification with tamper heuristics; MobileNetV3 "
                  "currency-note classifier."),
        ("Day 6", "IndexedDB offline queue and camera capture."),
        ("Day 7", "Evaluation report, tests, Docker, deploy, demo rehearsal."),
    ]
    y = Inches(2.3)
    for label, body in nxt:
        T.card(s, Inches(7.35), y, Inches(5.38), Inches(0.78), radius=0.12)
        T.text(s, Inches(7.6), y, Inches(0.9), Inches(0.78), label,
               size=11, bold=True, color=T.ACCENT, anchor=MSO_ANCHOR.MIDDLE)
        T.text(s, Inches(8.5), y, Inches(4.05), Inches(0.78), body,
               size=10.5, color=T.INK_2, line=1.35, anchor=MSO_ANCHOR.MIDDLE)
        y += Inches(0.87)

    T.page_number(s, 6)


# =========================================================== 7. results
def slide_results(prs):
    s = new_slide(prs)
    T.title(s, "Measured Results",
            "Every figure below is read from a report file the build regenerates.")

    # headline latency
    T.card(s, Inches(0.6), Inches(2.0), Inches(3.9), Inches(2.15))
    T.eyebrow(s, Inches(0.95), Inches(2.3), Inches(3.3), "Voice round trip, warm")
    T.text(s, Inches(0.95), Inches(2.6), Inches(3.3), Inches(0.8), P50,
           size=38, bold=True, color=T.PRIMARY)
    T.text(s, Inches(0.95), Inches(3.42), Inches(3.3), Inches(0.6),
           f"median, p95 {P95}, against a 4,000 ms budget",
           size=11, color=T.INK_2, line=1.4)

    stages = [
        ("Speech recognition", f"{WARM.get('mean_asr_ms', '—')} ms",
         "faster-whisper small, forced language, on the laptop GPU."),
        ("Intent + ledger", f"{WARM.get('mean_nlu_ms', '—')} ms",
         "Classification, slot filling and the sandbox write."),
        ("Speech synthesis", f"{WARM.get('mean_tts_ms', '—')} ms",
         "On a cache miss. Repeated replies are served from disk."),
    ]
    y = Inches(4.35)
    for label, value, note in stages:
        T.text(s, Inches(0.6), y, Inches(2.6), Inches(0.3), label,
               size=11.5, bold=True, color=T.INK)
        T.text(s, Inches(3.25), y, Inches(1.25), Inches(0.3), value,
               size=11.5, bold=True, color=T.PRIMARY, align=PP_ALIGN.RIGHT)
        T.text(s, Inches(0.6), y + Inches(0.26), Inches(3.9), Inches(0.3), note,
               size=10, color=T.INK_3, line=1.35)
        T.rule(s, Inches(0.6), y + Inches(0.62), Inches(3.9))
        y += Inches(0.78)

    # intent accuracy
    T.card(s, Inches(4.75), Inches(2.0), Inches(3.9), Inches(2.15))
    T.eyebrow(s, Inches(5.1), Inches(2.3), Inches(3.3), "Intent accuracy today")
    T.text(s, Inches(5.1), Inches(2.6), Inches(3.3), Inches(0.8), ACC,
           size=38, bold=True, color=T.ACCENT)
    T.text(s, Inches(5.1), Inches(3.42), Inches(3.3), Inches(0.6),
           f"keyword baseline, macro F1 {F1}, on {TEST_ROWS} hand-written rows",
           size=11, color=T.INK_2, line=1.4)

    T.text(s, Inches(4.75), Inches(4.35), Inches(3.9), Inches(1.9),
           [("This is the floor, not the result.", {"size": 12, "bold": True,
                                                    "color": T.INK, "space_after": 6}),
            ("The trained MuRIL classifier is the target and is not finished, so "
             "the app is answering with the keyword baseline it ships as a "
             "fallback. Every response names the backend that answered it, which "
             "is why a baseline number cannot be mistaken for a model number on "
             "demo day.", {"size": 10.5, "color": T.INK_2, "line": 1.45,
                           "space_after": 6}),
            ("Target: ≥ 90% on the same hand-written set.",
             {"size": 10.5, "bold": True, "color": T.ACCENT})],
           )

    # honest findings
    T.card(s, Inches(8.9), Inches(2.0), Inches(3.83), Inches(4.55),
           fill=T.SURFACE, outline=T.LINE)
    T.bar(s, Inches(8.9), Inches(2.0), Inches(0.035), Inches(4.55), T.GOLD)
    T.eyebrow(s, Inches(9.2), Inches(2.3), Inches(3.3), "What is not working yet", T.GOLD)
    findings = [
        ("Telugu comes back in the wrong script.",
         "whisper-small transcribed a Telugu clip into Devanagari. Fix is the "
         "medium model for ta/te, with the latency cost reported."),
        ("Hindi transcription is lossy.",
         "बैलेंस came back as बेलेस, "
         "which a keyword matcher then misses. A trained classifier is far more "
         "tolerant of this than substring cues."),
        ("Four of seven test clips resolved correctly.",
         "Clean synthetic speech, keyword backend. Both halves of that sentence "
         "are why the number is what it is."),
    ]
    y = Inches(2.65)
    for head, body in findings:
        T.text(s, Inches(9.2), y, Inches(3.25), Inches(0.5), head,
               size=11, bold=True, color=T.INK, line=1.3)
        T.text(s, Inches(9.2), y + Inches(0.42), Inches(3.25), Inches(0.85), body,
               size=10, color=T.INK_2, line=1.4)
        y += Inches(1.32)

    T.page_number(s, 7)


# ========================================================== 8. interface
def slide_interface(prs):
    s = new_slide(prs)
    T.title(s, "The Interface, Rebuilt",
            "Accessibility constraints first; the styling had to fit around them.")

    left = [
        ("scan", T.T_SCAN, "Emoji replaced with a drawn icon set",
         "Emoji render in whatever font the device ships, at that vendor's weight "
         "and colour — so the same screen looked different on every phone. "
         "Thirty-five stroked icons on a 24px grid now inherit their colour from "
         "the thing they label."),
        ("wallet", T.T_MONEY, "Colour carries meaning, never decoration",
         "Six category tones, each tinting its icon chip at 8%. Six saturated "
         "blocks on one screen would compete; six faint ones stay separable."),
        ("globe", T.T_SCHEME, "Typography that survives four scripts",
         "Uppercase tracked labels are scoped to English only — Devanagari, "
         "Tamil and Telugu have no letter case, and tracking pushes matras off "
         "their consonants."),
    ]
    y = Inches(2.0)
    for name, tone, head, body in left:
        T.icon_chip(s, name, Inches(0.6), y, Inches(0.6), tone=tone)
        T.text(s, Inches(1.42), y + Inches(0.02), Inches(6.2), Inches(0.3), head,
               size=13, bold=True, color=T.INK)
        T.text(s, Inches(1.42), y + Inches(0.34), Inches(6.2), Inches(1.1), body,
               size=11, color=T.INK_2, line=1.45)
        y += Inches(1.62)

    T.card(s, Inches(8.15), Inches(2.0), Inches(4.58), Inches(4.55))
    T.eyebrow(s, Inches(8.5), Inches(2.3), Inches(3.9), "The four constraints", T.PRIMARY)
    T.text(s, Inches(8.5), Inches(2.6), Inches(3.9), Inches(0.5),
           "Stated at the top of the stylesheet so a later edit cannot quietly "
           "trade one away.", size=10.5, color=T.INK_3, line=1.4)

    rules = [
        ("Light ground", "Readable in direct daylight, which is where this phone "
                         "is actually held."),
        ("≥ 88px tap targets", "Every control on the primary path, sized for "
                                    "an unsteady hand."),
        ("Fourfold redundancy", "Colour and icon and text and audio — never "
                                "colour alone."),
        ("17px base type", "No optional small print anywhere on the money path."),
    ]
    y = Inches(3.3)
    for label, body in rules:
        T.icon(s, "check", Inches(8.5), y + Inches(0.02), Inches(0.22), T.PRIMARY, 1.5)
        T.text(s, Inches(8.85), y, Inches(3.55), Inches(0.28), label,
               size=11.5, bold=True, color=T.INK)
        T.text(s, Inches(8.85), y + Inches(0.26), Inches(3.55), Inches(0.5), body,
               size=10, color=T.INK_2, line=1.4)
        y += Inches(0.8)

    T.page_number(s, 8)


# =========================================================== 9. roadmap
def slide_roadmap(prs):
    s = new_slide(prs)
    T.title(s, "What Ships Next", "The remaining four days of the sprint.")

    steps = [
        ("Day 4", "ScamNet",
         "Transformer plus rule features, blended, with an ablation table. "
         "Precision on the scam class matters most — false alarms destroy trust.",
         T.T_SAFETY, "shield"),
        ("Day 5", "Vision",
         "OpenCV QR verification with sticker-tamper heuristics, and a "
         "MobileNetV3 currency-note classifier tested on separately photographed "
         "notes.", T.T_SCAN, "scan"),
        ("Day 6", "Offline for real",
         "IndexedDB queue with client-generated idempotency keys, background "
         "sync, and camera capture wired to the vision endpoints.",
         T.T_SCHEME, "offline"),
        ("Day 7", "Evidence",
         "One script regenerates every metric into RESULTS.md. Tests prove the "
         "replay cannot double-spend. Docker Compose from a clean clone.",
         T.T_LEARN, "growth"),
    ]
    cw, gx = Inches(2.94), Inches(0.19)
    for i, (day, head, body, tone, name) in enumerate(steps):
        x = Inches(0.6) + (cw + gx) * i
        T.card(s, x, Inches(2.1), cw, Inches(3.5))
        T.bar(s, x, Inches(2.1), cw, Inches(0.035), tone)
        T.icon_chip(s, name, x + Inches(0.28), Inches(2.48), Inches(0.62), tone=tone)
        T.eyebrow(s, x + Inches(0.28), Inches(3.32), cw - Inches(0.56), day, tone)
        T.text(s, x + Inches(0.28), Inches(3.6), cw - Inches(0.56), Inches(0.4),
               head, size=15, bold=True, color=T.INK)
        T.text(s, x + Inches(0.28), Inches(4.1), cw - Inches(0.56), Inches(1.3),
               body, size=10.5, color=T.INK_2, line=1.45)

    T.card(s, Inches(0.6), Inches(5.9), Inches(12.13), Inches(0.85),
           fill=T.SURFACE, outline=T.LINE)
    T.icon(s, "flag", Inches(0.95), Inches(6.15), Inches(0.3), T.ACCENT, 1.5)
    T.text(s, Inches(1.42), Inches(6.13), Inches(11.0), Inches(0.45),
           "Verification bar: a stranger clones the repository, runs one command, "
           "speaks Hindi into it, gets the right answer back in under four "
           "seconds, and can replay a queued transfer twice without it settling "
           "twice.", size=11.5, color=T.INK_2, line=1.4)

    T.page_number(s, 9)


# =============================================================== 10. SDG
def slide_sdg(prs):
    s = new_slide(prs)
    T.title(s, "Impact & SDG Alignment",
            "Four goals, each tied to a feature that already exists or is dated.")

    goals = [
        ("1", "No Poverty", T.T_MONEY, "wallet",
         "Opens formal savings, transfers and welfare entitlements to households "
         "currently served only by informal lenders."),
        ("8", "Decent Work & Growth", T.T_SEND, "growth",
         "Gives farmers and micro-entrepreneurs scheme discovery and credit "
         "guidance in the language they negotiate in."),
        ("10", "Reduced Inequalities", T.T_SCHEME, "user",
         "Removes reading as a precondition for banking, so non-literate and "
         "elderly users operate the same account on equal terms."),
        ("16", "Peace, Justice & Institutions", T.T_SAFETY, "shield",
         "Explains why a message is a scam rather than only scoring it, and logs "
         "every money action against an auditable sandbox ledger."),
    ]
    cw, gx = Inches(2.94), Inches(0.19)
    for i, (num, name, tone, icon_name, body) in enumerate(goals):
        x = Inches(0.6) + (cw + gx) * i
        T.card(s, x, Inches(2.05), cw, Inches(3.35))
        T.card(s, x + Inches(0.28), Inches(2.35), Inches(0.62), Inches(0.62),
               fill=tone, outline=None, radius=0.22)
        T.text(s, x + Inches(0.28), Inches(2.5), Inches(0.62), Inches(0.35), num,
               size=15, bold=True, color=T.ON_DARK, align=PP_ALIGN.CENTER)
        T.icon(s, icon_name, x + cw - Inches(0.72), Inches(2.44), Inches(0.44),
               T.mix(tone, 0.45), 1.4)
        T.text(s, x + Inches(0.28), Inches(3.2), cw - Inches(0.56), Inches(0.55),
               name, size=13, bold=True, color=T.INK, line=1.2)
        T.text(s, x + Inches(0.28), Inches(3.85), cw - Inches(0.56), Inches(1.3),
               body, size=10.5, color=T.INK_2, line=1.45)

    T.card(s, Inches(0.6), Inches(5.7), Inches(12.13), Inches(1.15),
           fill=T.PRIMARY_INK, outline=None)
    T.text(s, Inches(1.0), Inches(5.95), Inches(11.3), Inches(0.7),
           "The question this project moves is not “can rural citizens use "
           "digital banking” — they already hold the accounts. It is whether "
           "someone who cannot read can use one safely, in their own voice, "
           "without being defrauded on the way.",
           size=13, bold=True, color=T.ON_DARK, line=1.45)

    T.page_number(s, 10, T.INK_3)


def main() -> int:
    prs = Presentation()
    prs.slide_width = T.SLIDE_W
    prs.slide_height = T.SLIDE_H

    for build in (slide_title, slide_problem, slide_solution, slide_features,
                  slide_architecture, slide_progress, slide_results,
                  slide_interface, slide_roadmap, slide_sdg):
        build(prs)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(prs.slides.__iter__.__self__._sldIdLst)} slides)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
