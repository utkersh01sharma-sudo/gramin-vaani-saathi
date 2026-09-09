# -*- coding: utf-8 -*-
"""Text to speech: gTTS, with a content-addressed disk cache.

The app says the same few dozen sentences over and over -- "your balance is",
"I did not catch that", the six tile labels. Synthesising those repeatedly would
add a network round trip to Google for every reply, which is both slow and, on a
rural connection, the least reliable part of the whole pipeline.

So the cache key is a hash of (text, language, slow) and the file name *is* that
hash. This has three consequences worth stating:

* a repeated reply costs a stat() call, not a request;
* two workers synthesising the same sentence at the same time write the same
  bytes to the same path, so there is no coordination problem;
* the cache never goes stale, because changing the text changes the key.

Failure is not an error condition here. gTTS needs the internet, and this app is
explicitly built for people who often do not have it. When synthesis fails the
adapter returns ``None`` and the PWA speaks the same string with the browser's
own SpeechSynthesis voice. The user hears the sentence either way; only the voice
changes. That fallback is the offline story, not a patch over a bug.
"""
from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path

from django.conf import settings

from ..base import TTSAdapter

logger = logging.getLogger(__name__)

# gTTS locale codes. Hindi and Tamil are plain; Telugu is only served under the
# bare code, and English is pinned to en-IN so numbers and names are read with
# Indian phrasing ("five hundred rupees", not "five hundred dollars"-cadence).
GTTS_LANG = {"hi": "hi", "en": "en", "ta": "ta", "te": "te"}
GTTS_TLD = {"en": "co.in", "hi": "co.in", "ta": "co.in", "te": "co.in"}

CACHE_SUBDIR = "tts"


def cache_key(text: str, language: str, slow: bool) -> str:
    raw = f"{language}|{int(slow)}|{text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


class GttsTTS(TTSAdapter):
    """Google Translate TTS with an on-disk cache under MEDIA_ROOT/tts/."""

    name = "gtts"

    def __init__(self) -> None:
        self._dir = Path(settings.MEDIA_ROOT) / CACHE_SUBDIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._hits = 0
        self._misses = 0

    @property
    def stats(self) -> dict:
        return {"hits": self._hits, "misses": self._misses}

    def synthesize(self, text: str, language: str, slow: bool = False) -> str | None:
        """Return a MEDIA_URL-relative path, or None if the caller should fall
        back to the browser voice."""
        text = (text or "").strip()
        if not text:
            return None

        lang = GTTS_LANG.get(language, "hi")
        key = cache_key(text, lang, slow)
        path = self._dir / f"{key}.mp3"
        rel = f"{CACHE_SUBDIR}/{key}.mp3"

        if path.exists() and path.stat().st_size > 0:
            self._hits += 1
            return rel

        try:
            from gtts import gTTS
        except ImportError:
            logger.warning("gTTS is not installed -- replies fall back to the browser voice")
            return None

        started = time.perf_counter()
        try:
            # Write through a per-attempt temp name and rename into place, so a
            # connection that dies mid-download cannot leave a truncated mp3
            # sitting at the cache key where every later request would find it.
            tmp = path.with_suffix(f".{int(time.time() * 1000)}.part")
            gTTS(text=text, lang=lang, tld=GTTS_TLD.get(lang, "com"), slow=slow).save(str(tmp))
            tmp.replace(path)
        except Exception as exc:
            logger.warning("TTS unavailable (%s: %s) -- browser voice will be used",
                           type(exc).__name__, exc)
            return None

        self._misses += 1
        logger.info("TTS synthesised %d chars of %s in %.2fs", len(text), lang,
                    time.perf_counter() - started)
        return rel


class NullTTS(TTSAdapter):
    """Always defers to the browser voice.

    Used by tests and by the offline-first deployment profile, where paying for a
    network round trip to render a sentence the device can already speak is the
    wrong trade.
    """

    name = "null"

    def synthesize(self, text: str, language: str, slow: bool = False) -> None:
        return None
