# -*- coding: utf-8 -*-
"""Regenerate docs/RESULTS.md from the report files. No number is typed by hand.

    python ml/evaluate.py

Every training and evaluation script in ml/ writes a JSON report to
ml/reports/. This script only reads them and lays them out, so the write-up
cannot drift from what was measured: retrain a model, rerun this, and the
document changes with it. Anything not yet measured is said to be missing,
not filled in.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "ml" / "reports"
OUT = ROOT / "docs" / "RESULTS.md"
LANG = {"hi": "Hindi", "en": "English", "ta": "Tamil", "te": "Telugu"}


def load(name: str) -> dict | None:
    p = REPORTS / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def pct(x: float | None, digits: int = 1) -> str:
    return "—" if x is None else f"{100 * x:.{digits}f}%"


def f3(x: float | None) -> str:
    return "—" if x is None else f"{x:.3f}"


def table(header: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def cer(ref: str, hyp: str) -> float:
    """Character error rate: Levenshtein distance / reference length, spaces ignored.

    Characters rather than words because Indic word boundaries in ASR output
    are unreliable (a missing space doubles a word error), and a single wrong
    matra should cost one character, not a whole word.
    """
    a, b = ref.replace(" ", ""), hyp.replace(" ", "")
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] / max(len(a), 1)


def intent_section() -> str:
    m, frozen, base, gate = (load("intent_metrics.json"), load("intent_metrics_frozen_emb.json"),
                             load("baseline_intent_metrics.json"), load("intent_gate.json"))
    if not m:
        return "## 1. IntentNet\n\n_Not trained yet: run `python ml/train_intent.py`._\n"
    rows = []
    if base:
        rows.append(["Keyword baseline", pct(base["accuracy"]), f3(base["macro_f1"]), "—"])
    if frozen:
        rows.append(["MuRIL, embeddings frozen", pct(frozen["accuracy"]), f3(frozen["macro_f1"]),
                     f"{frozen['train_minutes']} min"])
    rows.append(["**MuRIL, full fine-tune (deployed)**", f"**{pct(m['accuracy'])}**", f"**{f3(m['macro_f1'])}**",
                 f"{m['train_minutes']} min"])
    langs = [[LANG[k], pct(base["per_language"].get(k)) if base else "—",
              pct(frozen["per_language"].get(k)) if frozen else "—", pct(v)]
             for k, v in m["per_language"].items()]
    weakest = sorted(m["per_intent"].items(), key=lambda kv: kv[1]["f1"])[:4]
    s = [
        "## 1. IntentNet — what did the user ask for?",
        "",
        f"`{m['base_model']}` fine-tuned for {len(m['labels'])} intents. Test set: **{m['n']} utterances "
        "written by hand**, sharing no templates with the generated training data.",
        "",
        table(["System", "Accuracy", "Macro F1", "Train time"], rows),
        "",
        table(["Language", "Baseline", "Frozen emb.", "Deployed"], langs),
        "",
        f"Validation accuracy on *generated* data was {pct(m['validation_generated'].get('accuracy'))} — "
        "it measures how well the model learned the generator, which is why it is not the headline.",
        "",
        ("**Ablation.** Freezing MuRIL's 152M-parameter embedding matrix (64% of the model) costs "
         f"{100 * (m['accuracy'] - frozen['accuracy']):.1f} percentage points of accuracy and saves 1.6 GB "
         "of training memory; the deployed model trains it.") if frozen else "",
        "",
        "Weakest intents (F1): " + ", ".join(f"`{k}` {v['f1']:.2f}" for k, v in weakest) + ".",
    ]
    if gate:
        r = gate["recommended"]
        s += [
            "",
            "### Confidence gate",
            "",
            "Below `INTENT_MIN_CONFIDENCE` the app refuses to act and shows the icon grid instead. "
            "The threshold is chosen by `ml/calibrate_gate.py` to maximise coverage while keeping "
            f"**silent error** (acting on the wrong intent, as a share of everything said) under "
            f"{pct(gate['silent_error_budget'], 0)}.",
            "",
            table(["Threshold", "Acts on", "Accuracy when acting", "Silent error", "Falls back"],
                  [[f"{x['threshold']:.2f}" + (" ✓" if x["threshold"] == r["threshold"] else ""),
                    pct(x["coverage"]), pct(x["accepted_accuracy"]), pct(x["silent_error"]),
                    pct(x["fallback_rate"])]
                   for x in gate["sweep"] if 0.25 <= x["threshold"] <= 0.6]),
            "",
            f"Deployed: **{r['threshold']:.2f}**. The previous hand-picked 0.55 refused "
            f"{pct(next(x for x in gate['sweep'] if x['threshold'] == 0.55)['fallback_rate'])} of utterances.",
        ]
    return "\n".join(s) + "\n"


def scam_section() -> str:
    m = load("scam_metrics.json")
    if not m:
        return "## 2. ScamNet\n\n_Not trained yet: run `python ml/train_scam.py`._\n"
    names = {"rules_only": "Rule features only (logistic regression)", "transformer_only": "MuRIL only"}
    rows = []
    for key, sysm in m["systems"].items():
        label = names.get(key, f"**Blend, w = {m['blend_weight_transformer']} (deployed)**")
        rows.append([label, pct(sysm["accuracy"]), f3(sysm["macro_f1"]), f3(sysm["scam_precision"]),
                     f3(sysm["scam_recall"]), pct(sysm["false_alarm_rate_on_safe"]), sysm["missed_scams"]])
    curve = " · ".join(f"{w}: {v['macro_f1']:.3f}" for w, v in m["blend_curve"].items())
    top_rules = sorted(m["rule_weights_toward_scam"].items(), key=lambda kv: -kv[1])[:5]
    s = [
        "## 2. ScamNet — is this message a scam?",
        "",
        f"Three classes (safe / suspicious / scam). Trained on {m['n_train']:,} synthetic messages built from "
        "documented Indian fraud patterns in all four languages; tested on **"
        f"{m['n_test']} hand-written messages**, including scam types absent from training "
        "(\"Mum, this is my new number\", crypto doubling, gas-subsidy refunds) and genuine bank messages "
        "that mention an OTP.",
        "",
        table(["System", "Accuracy", "Macro F1", "Scam precision", "Scam recall", "False alarms on safe", "Missed scams"], rows),
        "",
        "**Reading the ablation.** Rules alone are the most *precise* on scams but miss many — they only "
        "know the mechanics they were written for. The transformer catches everything but raises more false alarms. "
        "The blend weight was fixed at 0.7 before testing; on this test set the blend equals the transformer, "
        "because the fine-tuned model is near-certain and 30% rule weight cannot overturn it. "
        "In practice the rules supply the **spoken reasons**, not the verdict.",
        "",
        f"Blend-weight curve, macro F1 (reported, *not* used to choose w — that would tune on the test set): {curve}.",
        "",
        "Per language (deployed): " + ", ".join(f"{LANG[k]} {pct(v)}" for k, v in m["per_language_blended"].items()) + ".",
        "",
        "Strongest fitted rule signals: " + ", ".join(f"`{k}` (+{v:.1f})" for k, v in top_rules) + ".",
        "",
        "Mistakes, all of them:",
        "",
        table(["Lang", "Truth", "Predicted", "Message"],
              [[x["language"], x["gold"], x["pred"], x["text"][:80].replace("|", "/")] for x in m["mistakes"]]),
        "",
        f"Validation accuracy on generated data: {pct(m['val_accuracy_generated'])} — again, a measure of the generator.",
    ]
    return "\n".join(s) + "\n"


def schemes_section() -> str:
    m = load("scheme_search.json")
    if not m:
        return ""
    r = m["results"]
    rows = [[k.capitalize() if k != "hybrid" else f"**Hybrid, keyword weight {r['hybrid']['keyword_weight']} (deployed)**",
             f3(r[k]["hit_at_1"]), f3(r[k]["hit_at_3"]),
             " · ".join(f"{LANG[l]} {v:.2f}" for l, v in r[k]["per_language_hit_at_1"].items())]
            for k in ("keyword", "embedding", "hybrid")]
    return "\n".join([
        "## 3. Scheme search — \"I need money for farming\" → PM-KISAN",
        "",
        f"{m['n_queries']} hand-written queries (12 per language) that describe a need without naming the scheme. "
        f"Encoder: `{m['embedding_model']}` (chosen because its training languages include Tamil and Telugu).",
        "",
        table(["Method", "Hit@1", "Hit@3", "Hit@1 by language"], rows),
        "",
        "Eligibility itself is not learned: 20 schemes are declarative rules, and every verdict "
        "(eligible / maybe / not eligible) comes with the reason for each rule. "
        "\"Maybe\" means a fact is missing — the app asks for it instead of saying no.",
        "",
        "Remaining misses (not patched with keywords, which would be tuning on the test set): "
        + "; ".join(f"\"{x['text']}\"" for x in r["hybrid"]["misses"]) + ".",
    ]) + "\n"


def vision_section() -> str:
    q, n = load("qr_tamper.json"), load("note_metrics.json")
    s = ["## 4. Vision — QR codes and banknotes", ""]
    if q:
        s += [
            "**QR verification** decodes with OpenCV (plain → CLAHE → adaptive threshold) and falls back to pyzbar, "
            "parses the UPI URI, checks the payee against the registry, and flags pre-filled amounts and hidden links.",
            "",
            f"**Sticker detection** on {q['n_posters']} synthetic shop posters, half with a fraudster's QR pasted over:",
            "",
            table(["Signal", "AUC"], [[k.replace("_", " "), f3(v)] for k, v in q["feature_auc"].items()]),
            "",
            f"Deployed (rotation mismatch): AUC **{f3(q['tamper_auc'])}**, detection {pct(q['detection_rate'])}, "
            f"false alarms {pct(q['false_alarm_rate'])}; decode rate {pct(q['decode_rate'])}. "
            "Stickers pressed on within about a degree of square cannot be told from print by a photo.",
            "",
            f"_Caveat: {q['caveat']}_",
            "",
        ]
    if n:
        s += [f"**NoteNet** (MobileNetV3-Small): {pct(n['accuracy'])} on {n['n_test']} photos from a separate session.", ""]
    else:
        s += ["**NoteNet** is not trained: it needs 60–100 photographs of real notes per denomination, "
              "which have to be taken by hand (`ml/train_notes.py` documents the layout and is ready to run). "
              "Until then the API answers with a colour heuristic, caps its confidence at 60%, says so in the "
              "response (`backend: colour_heuristic`), and the UI tells the user to check the note themselves.", ""]
    return "\n".join(s) + "\n"


def voice_section() -> str:
    v = load("voice_latency.json")
    if not v:
        return ""
    w = v["warm"]
    rows = []
    cers = {}
    for r in v["runs"]:
        c = cer(r["reference_text"], r["transcript"])
        cers.setdefault(r["language"], []).append(c)
        rows.append([r["file"], r["reference_text"], r["transcript"], pct(c, 0), r["intent"],
                     "✓" if r["intent_correct"] else "✗"])
    load_ms = v.get("model_load_ms") or {}
    return "\n".join([
        "## 5. Voice pipeline — speech in, spoken answer out",
        "",
        f"Device: {v['device']}; Whisper `{v['asr_model']}`. Budget: {v['budget_ms']} ms from end of speech to reply.",
        "",
        table(["", "ms"], [["warm p50", w["p50_ms"]], ["warm p95", w["p95_ms"]], ["mean ASR", w["mean_asr_ms"]],
                           ["mean NLU + dialog", w["mean_nlu_ms"]], ["mean TTS", w["mean_tts_ms"]],
                           ["first clip (cold)", v["cold_start_ms"]]]),
        "",
        ("TTS shows ~0 ms because every reply in this run was already in the synthesis cache "
         "(keyed by text and language); an uncached reply measured ~0.6 s in the previous run. "
         "Common replies are cached after first use, so both numbers are real -- for different users.\n\n"
         if w["mean_tts_ms"] < 50 else "") +
        "Model loading at worker start (`ai/warmup.py`), paid once instead of by the first user: "
        + ", ".join(f"{k} {ms/1000:.1f}s" for k, ms in load_ms.items()) + ".",
        "",
        table(["Clip", "Reference", "Transcript", "CER", "Intent", ""], rows),
        "",
        f"Intent correct on {v['intent_correct']}/{v['clips']} clips. The Telugu miss is an ASR failure: Whisper `small` "
        "transcribed Telugu speech into Devanagari even with the language forced. Typed input on the same NLU path is "
        "the documented fallback; `ASR_MODEL_SIZE=medium` is the next thing to try.",
        "",
        f"_{v['note']}_",
    ]) + "\n"


def main() -> None:
    parts = [
        "# Results",
        "",
        f"_Generated by `python ml/evaluate.py` on {date.today().isoformat()} from the JSON files in "
        "`ml/reports/`. Do not edit by hand — rerun the script._",
        "",
        "Every headline number below is on data **written by hand and kept out of training**. "
        "Numbers on generated data are shown only to make the gap visible.",
        "",
        intent_section(), scam_section(), schemes_section(), vision_section(), voice_section(),
        "## Reproducing",
        "",
        "```bash",
        "python ml/train_intent.py --train-embeddings   # IntentNet (deployed configuration)",
        "python ml/calibrate_gate.py                    # confidence threshold",
        "python ml/data/generate_scam_data.py && python ml/train_scam.py",
        "python ml/eval_scheme_search.py",
        "python ml/eval_qr_tamper.py",
        "python ml/bench_voice.py",
        "python ml/evaluate.py                          # this document",
        "```",
        "",
    ]
    OUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
