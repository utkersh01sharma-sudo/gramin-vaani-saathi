# -*- coding: utf-8 -*-
"""Measure the voice pipeline end to end and write ml/reports/voice_latency.json.

The plan sets a < 4 s budget from "user stops speaking" to "reply starts
playing". A single average hides the two things that actually matter, so this
reports the breakdown per stage and the p50/p95 across clips:

    asr_ms   transcription -- dominated by model size and device
    nlu_ms   intent + slots + ledger work -- milliseconds, and should stay there
    tts_ms   synthesis -- a network round trip on a cache miss, ~0 on a hit

The first clip is discarded from the statistics and reported separately as
``cold_start_ms``, because it includes loading half a gigabyte of weights. That
cost is real but it is paid once per worker, not once per utterance, and folding
it into the average would misrepresent both numbers.

Run with the dev server stopped (it competes for the GPU):

    python ml/bench_voice.py
"""
from __future__ import annotations

import json
import os
import shutil
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "ml" / "data" / "audio_fixtures"
REPORT = ROOT / "ml" / "reports" / "voice_latency.json"

sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

# The Windows console defaults to cp1252, which cannot encode Devanagari, Tamil
# or Telugu -- printing a transcript would crash the run after the expensive part
# had already succeeded. The report file is UTF-8 regardless; this is only stdout.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def main() -> int:
    import django

    django.setup()

    from django.conf import settings
    from django.contrib.auth import get_user_model

    from apps.voice.tasks import process_audio

    manifest_path = FIXTURES / "manifest.json"
    if not manifest_path.exists():
        print("No fixtures. Run: python ml/data/make_audio_fixtures.py", file=sys.stderr)
        return 1
    clips = json.loads(manifest_path.read_text(encoding="utf-8"))

    User = get_user_model()
    user = User.objects.filter(is_superuser=False).order_by("pk").first()
    if user is None:
        print("No demo user. Run: python backend/manage.py seed_demo", file=sys.stderr)
        return 1

    runs = []
    for clip in clips:
        src = FIXTURES / clip["file"]
        if not src.exists() or src.stat().st_size == 0:
            print(f"SKIP {clip['file']} (missing or empty)", file=sys.stderr)
            continue
        # process_audio deletes its input once transcribed, which is the correct
        # behaviour for a real recording and the wrong behaviour for a fixture.
        work = Path(settings.MEDIA_ROOT) / "uploads" / "voice"
        work.mkdir(parents=True, exist_ok=True)
        tmp = work / f"bench_{clip['file']}"
        shutil.copy2(src, tmp)

        started = time.perf_counter()
        payload = process_audio(str(tmp), user.pk, clip["language"], None)
        wall_ms = int((time.perf_counter() - started) * 1000)

        runs.append(
            {
                "file": clip["file"],
                "language": clip["language"],
                "expected_intent": clip["intent"],
                "reference_text": clip["text"],
                "transcript": payload.get("transcript", ""),
                "intent": payload.get("intent"),
                "intent_correct": payload.get("intent") == clip["intent"],
                "asr_confidence": payload.get("asr_confidence"),
                "audio_seconds": payload.get("audio_seconds"),
                "nlu_backend": payload.get("nlu_backend"),
                "timings": payload.get("timings", {}),
                "wall_ms": wall_ms,
            }
        )
        ok = "OK " if runs[-1]["intent_correct"] else "MISS"
        print(f"{ok} {clip['file']:<16} {wall_ms:>6}ms  {payload.get('intent'):<20} "
              f"{payload.get('transcript', '')[:44]}")

    if not runs:
        print("No clips processed.", file=sys.stderr)
        return 1

    def pct(values: list[int], q: float) -> int:
        if not values:
            return 0
        ordered = sorted(values)
        return ordered[min(int(q * len(ordered)), len(ordered) - 1)]

    warm = runs[1:] or runs
    totals = [r["timings"].get("total_ms", r["wall_ms"]) for r in warm]

    report = {
        "device": _device_label(),
        "asr_model": settings.ASR_MODEL_SIZE,
        "clips": len(runs),
        "cold_start_ms": runs[0]["timings"].get("total_ms", runs[0]["wall_ms"]),
        "warm": {
            "p50_ms": int(statistics.median(totals)),
            "p95_ms": pct(totals, 0.95),
            "mean_ms": int(statistics.fmean(totals)),
            "mean_asr_ms": int(statistics.fmean(
                [r["timings"].get("asr_ms", 0) for r in warm])),
            "mean_nlu_ms": int(statistics.fmean(
                [r["timings"].get("nlu_ms", 0) for r in warm])),
            "mean_tts_ms": int(statistics.fmean(
                [r["timings"].get("tts_ms", 0) for r in warm])),
        },
        "intent_correct": sum(r["intent_correct"] for r in runs),
        "budget_ms": 4000,
        "note": (
            "Clips are gTTS-rendered, i.e. clean studio speech. These numbers are "
            "a latency floor and a wiring check, not an accuracy result. Word "
            "error rate must be measured on phone recordings of real speakers."
        ),
        "runs": runs,
    }

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    w = report["warm"]
    print(f"\ncold start {report['cold_start_ms']}ms | warm p50 {w['p50_ms']}ms "
          f"p95 {w['p95_ms']}ms (budget {report['budget_ms']}ms)")
    print(f"  asr {w['mean_asr_ms']}ms  nlu {w['mean_nlu_ms']}ms  tts {w['mean_tts_ms']}ms")
    print(f"  intent correct on {report['intent_correct']}/{report['clips']} clips")
    print(f"wrote {REPORT.relative_to(ROOT)}")
    return 0


def _device_label() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            return f"cuda ({torch.cuda.get_device_name(0)})"
    except Exception:
        pass
    return "cpu"


if __name__ == "__main__":
    raise SystemExit(main())
