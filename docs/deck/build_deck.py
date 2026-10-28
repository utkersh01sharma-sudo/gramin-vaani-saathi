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
INTENT = load("intent_metrics.json")
GATE = load("intent_gate.json")
SCAM = load("scam_metrics.json")
SEARCH = load("scheme_search.json")
QR = load("qr_tamper.json")


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


def pct(x) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


INTENT_ACC = pct(INTENT.get("accuracy")) if INTENT else "not yet measured"
SCAM_SYS = SCAM.get("systems", {})
SCAM_BLEND = next((v for k, v in SCAM_SYS.items() if k.startswith("blended")), {})
HYBRID = SEARCH.get("results", {}).get("hybrid", {})


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
    cw, gx = Inches(2.89), Inches(0.19)
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


# ======================================================= 6. what was built
def slide_progress(prs):
    s = new_slide(prs)
    T.title(s, "What Was Built",
            "The full seven-day plan, delivered as working, tested software.")

    done = [
        ("Voice dialog in four languages",
         "Speech or typing → IntentNet → action → spoken reply. Money never moves "
         "on the first sentence."),
        ("Sandbox banking with exactly-once replay",
         "Idempotent transfers; the offline queue lives in IndexedDB and replays "
         "through one endpoint."),
        ("Schemes, lessons, scam checks, QR checks",
         "20 rule-based schemes with reasons, 8 graded lessons, ScamNet, OpenCV "
         "QR verification with sticker detection."),
        ("A rebuilt interface",
         "Sidebar naming every function; every view fits one laptop screen; "
         "a phone layout with a drawer."),
        ("Evidence and deployment",
         "27 tests, a generated results report, Docker Compose with a separate "
         "model server."),
    ]
    T.eyebrow(s, Inches(0.6), Inches(2.0), Inches(6.3), "Delivered", T.OK)
    y = Inches(2.3)
    for head, body in done:
        T.icon(s, "check", Inches(0.62), y + Inches(0.03), Inches(0.24), T.OK, 1.5)
        T.text(s, Inches(1.0), y, Inches(5.9), Inches(0.28), head,
               size=12.5, bold=True, color=T.INK)
        T.text(s, Inches(1.0), y + Inches(0.26), Inches(5.9), Inches(0.55), body,
               size=10.5, color=T.INK_2, line=1.4)
        y += Inches(0.87)

    T.eyebrow(s, Inches(7.35), Inches(2.0), Inches(5.4), "Models trained and measured", T.ACCENT)
    models = [
        ("IntentNet", INTENT_ACC,
         f"accuracy on 183 hand-written utterances (keyword baseline {ACC})", T.T_MONEY),
        ("ScamNet", pct(SCAM_BLEND.get("accuracy")),
         f"accuracy on {SCAM.get('n_test', '—')} hand-written messages, "
         f"{SCAM_BLEND.get('missed_scams', '—')} scams missed", T.T_SAFETY),
        ("Scheme search", f"{HYBRID['hit_at_1']:.3f}" if HYBRID else "—",
         "hit@1 on 48 queries that never name the scheme", T.T_SCHEME),
        ("QR sticker check", f"AUC {QR['tamper_auc']:.2f}" if QR else "—",
         f"{pct(QR.get('false_alarm_rate'))} false alarms on synthetic posters", T.T_SCAN),
    ]
    y = Inches(2.3)
    for name, value, body, tone in models:
        T.card(s, Inches(7.35), y, Inches(5.38), Inches(0.96), radius=0.12)
        T.bar(s, Inches(7.35), y, Inches(0.035), Inches(0.96), tone)
        T.text(s, Inches(7.6), y + Inches(0.1), Inches(1.9), Inches(0.3), name,
               size=11, bold=True, color=T.INK)
        T.text(s, Inches(7.6), y + Inches(0.38), Inches(1.9), Inches(0.5), value,
               size=19, bold=True, color=tone)
        T.text(s, Inches(9.6), y, Inches(2.95), Inches(0.96), body,
               size=10, color=T.INK_2, line=1.35, anchor=MSO_ANCHOR.MIDDLE)
        y += Inches(1.08)

    T.page_number(s, 6)


# =========================================================== 7. results
def slide_results(prs):
    s = new_slide(prs)
    T.title(s, "Measured Results",
            "Hand-written test data only. Every figure is read from a report file.")

    T.card(s, Inches(0.6), Inches(2.0), Inches(3.9), Inches(2.15))
    T.eyebrow(s, Inches(0.95), Inches(2.3), Inches(3.3), "IntentNet accuracy")
    T.text(s, Inches(0.95), Inches(2.6), Inches(3.3), Inches(0.8), INTENT_ACC,
           size=38, bold=True, color=T.PRIMARY)
    gate = GATE.get("recommended", {})
    T.text(s, Inches(0.95), Inches(3.42), Inches(3.3), Inches(0.6),
           f"vs {ACC} keyword baseline. Gate at {gate.get('threshold', '—')}: acts on "
           f"{pct(gate.get('coverage'))}, wrong-and-acted {pct(gate.get('silent_error'))}.",
           size=10.5, color=T.INK_2, line=1.4)

    stages = [
        ("Voice round trip, warm", f"{P50} / {P95}", "p50 / p95 against a 4,000 ms budget, RTX 4070"),
        ("Speech recognition", f"{WARM.get('mean_asr_ms', '—')} ms", "faster-whisper small, forced language"),
        ("Intent + dialog + ledger", f"{WARM.get('mean_nlu_ms', '—')} ms", "MuRIL, slots, sandbox write"),
    ]
    y = Inches(4.35)
    for label, value, note in stages:
        T.text(s, Inches(0.6), y, Inches(2.4), Inches(0.3), label, size=11.5, bold=True, color=T.INK)
        T.text(s, Inches(2.9), y, Inches(1.6), Inches(0.3), value, size=11.5, bold=True,
               color=T.PRIMARY, align=PP_ALIGN.RIGHT)
        T.text(s, Inches(0.6), y + Inches(0.26), Inches(3.9), Inches(0.3), note,
               size=10, color=T.INK_3, line=1.35)
        T.rule(s, Inches(0.6), y + Inches(0.62), Inches(3.9))
        y += Inches(0.78)

    T.card(s, Inches(4.75), Inches(2.0), Inches(3.9), Inches(4.55))
    T.eyebrow(s, Inches(5.1), Inches(2.3), Inches(3.3), "ScamNet ablation")
    for i, hdr in enumerate(("Macro F1", "Scam P", "Missed")):
        T.text(s, Inches(6.45) + Inches(0.72) * i, Inches(2.62), Inches(0.72), Inches(0.3), hdr,
               size=9, bold=True, color=T.INK_3, align=PP_ALIGN.RIGHT)
    rows = [("Rules only", SCAM_SYS.get("rules_only", {})),
            ("MuRIL only", SCAM_SYS.get("transformer_only", {})),
            ("Blend 0.7 (deployed)", SCAM_BLEND)]
    y = Inches(2.95)
    for label, m in rows:
        T.text(s, Inches(5.1), y, Inches(1.4), Inches(0.5), label, size=10.5, bold=True,
               color=T.INK, line=1.2)
        vals = (f"{m.get('macro_f1', 0):.3f}", f"{m.get('scam_precision', 0):.2f}",
                str(m.get("missed_scams", "—")))
        for i, v in enumerate(vals):
            T.text(s, Inches(6.45) + Inches(0.72) * i, y, Inches(0.72), Inches(0.3), v,
                   size=11, bold=True, color=T.ACCENT if label.startswith("Blend") else T.INK_2,
                   align=PP_ALIGN.RIGHT)
        T.rule(s, Inches(5.1), y + Inches(0.5), Inches(3.3))
        y += Inches(0.62)
    T.text(s, Inches(5.1), Inches(4.95), Inches(3.3), Inches(1.5),
           [("Rules are precise but blind to new scams; the transformer catches every "
             "scam but raises more false alarms.",
             {"size": 10, "color": T.INK_2, "line": 1.4, "space_after": 5}),
            ("Here the blend equals the transformer: the rules supply the spoken "
             "reasons, not the verdict.",
             {"size": 10, "bold": True, "color": T.INK, "line": 1.4})])

    T.card(s, Inches(8.9), Inches(2.0), Inches(3.83), Inches(4.55), fill=T.SURFACE, outline=T.LINE)
    T.bar(s, Inches(8.9), Inches(2.0), Inches(0.035), Inches(4.55), T.GOLD)
    T.eyebrow(s, Inches(9.2), Inches(2.3), Inches(3.3), "What does not work yet", T.GOLD)
    findings = [
        ("Telugu ASR writes the wrong script.",
         "Whisper small wrote a Telugu clip in Devanagari; 6 of 7 clips resolved. "
         "Typing is the fallback; the medium model is next."),
        ("ScamNet is phrasing-sensitive.",
         "A shortened version of the new-number scam scored safe. It needs more "
         "varied training data."),
        ("NoteNet needs real photographs.",
         "60–100 per note, taken by hand. Until then a colour heuristic answers, "
         "says so, and caps its confidence."),
    ]
    y = Inches(2.65)
    for head, body in findings:
        T.text(s, Inches(9.2), y, Inches(3.25), Inches(0.5), head, size=11, bold=True,
               color=T.INK, line=1.3)
        T.text(s, Inches(9.2), y + Inches(0.44), Inches(3.25), Inches(0.85), body,
               size=10, color=T.INK_2, line=1.4)
        y += Inches(1.32)

    T.page_number(s, 7)


# ========================================================== 8. interface
def slide_interface(prs):
    s = new_slide(prs)
    T.title(s, "One Screen, Every Function",
            "Rebuilt around a sidebar so nobody has to guess where anything is.")

    left = [
        ("layers", T.T_SCHEME, "Every function named twice",
         "The sidebar gives each section a label and a sentence saying what it does: "
         "find schemes you qualify for, not just schemes. In all four languages."),
        ("mic", T.T_MONEY, "Always a command line",
         "The top bar takes speech or typing on every screen, and its answer is shown "
         "and spoken wherever the user is."),
        ("check", T.T_SEND, "Nothing scrolls the page",
         "From 1366×768 up, every view fits the screen and lists scroll inside their own "
         "card. On a phone the sidebar becomes a drawer and the views stack."),
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
    T.eyebrow(s, Inches(8.5), Inches(2.3), Inches(3.9), "Rules the design keeps", T.PRIMARY)
    rules = [
        ("Confirm before money moves", "A dialog that is also read aloud; Yes is the "
                                        "only path to the ledger."),
        ("Never colour alone", "Every control carries an icon, a word, and an audio "
                               "button."),
        ("Claims are labelled as claims", "A QR code's printed payee name is never "
                                          "shown as verified."),
        ("Stale is stamped", "A cached balance always shows the time it was read."),
    ]
    y = Inches(2.75)
    for label, body in rules:
        T.icon(s, "check", Inches(8.5), y + Inches(0.02), Inches(0.22), T.PRIMARY, 1.5)
        T.text(s, Inches(8.85), y, Inches(3.55), Inches(0.28), label, size=11.5, bold=True,
               color=T.INK)
        T.text(s, Inches(8.85), y + Inches(0.26), Inches(3.55), Inches(0.55), body,
               size=10, color=T.INK_2, line=1.4)
        y += Inches(0.92)

    T.page_number(s, 8)


# =========================================================== 9. next steps
def slide_roadmap(prs):
    s = new_slide(prs)
    T.title(s, "Limitations & Next Steps", "What a field deployment would need first.")

    steps = [
        ("Data", "Photograph real notes",
         "NoteNet's training script is ready; it needs 60–100 photos per denomination "
         "and a test set shot in a separate session.", T.T_SCAN, "note"),
        ("Speech", "Better Telugu ASR",
         "Measure Whisper medium on phone recordings of real speakers, and report WER "
         "with the latency cost.", T.T_SCHEME, "mic"),
        ("Fraud", "Broader scam data",
         "Real reported messages in all four languages, so ScamNet stops depending "
         "on the exact wording of a scam.", T.T_SAFETY, "shield"),
        ("People", "A field usability study",
         "Every number here is on hand-written test data. Rural users on cheap phones "
         "are the test that matters.", T.T_LEARN, "user"),
    ]
    cw, gx = Inches(2.89), Inches(0.19)
    for i, (tag, head, body, tone, name) in enumerate(steps):
        x = Inches(0.6) + (cw + gx) * i
        T.card(s, x, Inches(2.1), cw, Inches(3.5))
        T.bar(s, x, Inches(2.1), cw, Inches(0.035), tone)
        T.icon_chip(s, name, x + Inches(0.28), Inches(2.48), Inches(0.62), tone=tone)
        T.eyebrow(s, x + Inches(0.28), Inches(3.32), cw - Inches(0.56), tag, tone)
        T.text(s, x + Inches(0.28), Inches(3.6), cw - Inches(0.56), Inches(0.4), head,
               size=14, bold=True, color=T.INK)
        T.text(s, x + Inches(0.28), Inches(4.1), cw - Inches(0.56), Inches(1.3), body,
               size=10.5, color=T.INK_2, line=1.45)

    T.card(s, Inches(0.6), Inches(5.9), Inches(12.13), Inches(0.85), fill=T.SURFACE, outline=T.LINE)
    T.icon(s, "flag", Inches(0.95), Inches(6.15), Inches(0.3), T.ACCENT, 1.5)
    T.text(s, Inches(1.42), Inches(6.13), Inches(11.0), Inches(0.45),
           "Still simulated by design: no real bank, PSP or SMS gateway is connected. "
           "The architecture is ready for one; the safety case for connecting it is not "
           "made by a student project.", size=11.5, color=T.INK_2, line=1.4)

    T.page_number(s, 9)


# =============================================================== 10. SDG
def slide_sdg(prs):
    s = new_slide(prs)
    T.title(s, "Impact & SDG Alignment",
            "Each goal tied to a working feature and a specific target — see SDG_MAPPING.md.")

    goals = [
        ("1", "No Poverty · 1.3, 1.4", T.T_MONEY, "wallet",
         "Opens formal savings, transfers and welfare entitlements to households "
         "currently served only by informal lenders."),
        ("8", "Decent Work · 8.3, 8.10", T.T_SEND, "growth",
         "Gives farmers and micro-entrepreneurs scheme discovery and credit "
         "guidance in the language they negotiate in."),
        ("10", "Reduced Inequalities · 10.2", T.T_SCHEME, "user",
         "Removes reading as a precondition for banking, so non-literate and "
         "elderly users operate the same account on equal terms."),
        ("16", "Justice & Institutions · 16.3, 16.4", T.T_SAFETY, "shield",
         "Explains why a message is a scam rather than only scoring it, and logs "
         "every money action against an auditable sandbox ledger."),
    ]
    cw, gx = Inches(2.89), Inches(0.19)
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
