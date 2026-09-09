# -*- coding: utf-8 -*-
"""Render a handful of spoken utterances so the audio path can be tested without
a microphone in the loop.

These are TTS clips, not field recordings, so they are *easier* than reality:
clean, noiseless, studio-cadence. They prove the pipeline is wired correctly and
give a latency floor. They do not prove accuracy -- the WER numbers in
docs/RESULTS.md have to come from clips of real people, recorded on a phone, and
hand-transcribed. Do not let a good number here stand in for that.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent / "audio_fixtures"

# (language, filename stem, what is said, the intent it should resolve to)
CLIPS = [
    ("hi", "hi_balance", "मेरा बैलेंस कितना है", "check_balance"),
    ("hi", "hi_send", "रमेश को पांच सौ रुपये भेज दो", "send_money"),
    ("hi", "hi_scheme", "मुझे खेती के लिए सरकारी योजना चाहिए", "find_scheme"),
    ("en", "en_balance", "how much money do I have in my account", "check_balance"),
    ("en", "en_scam", "is this message asking for my OTP a scam", "check_scam"),
    ("ta", "ta_balance", "என் கணக்கில் எவ்வளவு பணம் இருக்கு", "check_balance"),
    ("te", "te_balance", "నా ఖాతాలో ఎంత డబ్బు ఉంది", "check_balance"),
]


def main() -> int:
    try:
        from gtts import gTTS
    except ImportError:
        print("gTTS is not installed: pip install gTTS", file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for lang, stem, text, intent in CLIPS:
        path = OUT / f"{stem}.mp3"
        if path.exists() and path.stat().st_size > 0:
            print(f"kept  {path.name}")
        else:
            # gTTS is a network call and this connection drops often. Two
            # defences, both learned the hard way: retry, and write through a
            # temp file so a dropped connection cannot leave a zero-byte mp3
            # sitting at the real name, where the next run's existence check
            # would happily "keep" it and the decoder would reject it.
            for attempt in range(1, 5):
                tmp = path.with_suffix(".part")
                try:
                    gTTS(text=text, lang=lang, tld="co.in").save(str(tmp))
                    if tmp.stat().st_size == 0:
                        raise OSError("gTTS returned an empty file")
                    tmp.replace(path)
                    print(f"wrote {path.name}")
                    break
                except Exception as exc:
                    tmp.unlink(missing_ok=True)
                    print(f"  attempt {attempt} for {stem} failed: {exc}", file=sys.stderr)
                    time.sleep(2 * attempt)
            else:
                print(f"GIVING UP on {stem}", file=sys.stderr)
                continue
        manifest.append({"file": path.name, "language": lang, "text": text, "intent": intent})

    import json

    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"{len(manifest)} clips in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
