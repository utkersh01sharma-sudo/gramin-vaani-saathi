# -*- coding: utf-8 -*-
"""The audio pipeline, as a Celery task.

Everything expensive lives here rather than in a view, for one structural
reason: transcription holds a GPU and takes seconds, and a web worker that is
blocked on it cannot serve anyone else. Pushing it to a queue means the number of
people who can be *talking* at once is set by how many workers you run, not by
how many gunicorn threads you have, and the two can be scaled separately.

The stages are deliberately separable and separately timed:

    audio -> ASR -> dialog.handle -> TTS -> result

``dialog.handle`` is the same function ``/api/voice/text/`` calls. There is no
second copy of the decision logic for audio, so a rule about confirming payments
cannot drift between the two entry points.

Timings for every stage are returned with the result. The plan sets a < 4 s
end-to-end budget; a number you cannot see is a number you cannot defend, so the
API reports the breakdown rather than a pass/fail.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model

from ai.registry import get_asr, get_tts

from . import dialog

logger = logging.getLogger(__name__)


class _Stopwatch:
    """Records elapsed milliseconds per named stage."""

    def __init__(self) -> None:
        self.marks: dict[str, int] = {}
        self._t0 = time.perf_counter()
        self._last = self._t0

    def lap(self, name: str) -> None:
        now = time.perf_counter()
        self.marks[f"{name}_ms"] = int((now - self._last) * 1000)
        self._last = now

    def total(self) -> dict:
        self.marks["total_ms"] = int((time.perf_counter() - self._t0) * 1000)
        return self.marks


@shared_task(bind=True, name="voice.process_audio")
def process_audio(self, audio_path: str, user_id: int, language: str | None = None,
                  pending: dict | None = None) -> dict:
    """Transcribe, understand, act, and speak. Returns the full response dict."""
    clock = _Stopwatch()
    User = get_user_model()
    user = User.objects.select_related("profile").get(pk=user_id)

    # ---------------------------------------------------------------- ASR
    transcript = get_asr().transcribe(audio_path, language=language)
    clock.lap("asr")

    lang = language or transcript.language or settings.DEFAULT_LANGUAGE
    if lang not in settings.SUPPORTED_LANGUAGES:
        lang = settings.DEFAULT_LANGUAGE

    # Nothing came back, or what came back is not worth acting on. Say so and
    # offer the icon grid; never guess at an instruction that might move money.
    if not transcript.text or transcript.confidence < settings.ASR_MIN_CONFIDENCE:
        result = dialog.DialogResult(
            transcript=transcript.text,
            language=lang,
            intent="unknown",
            confidence=transcript.confidence,
            icon="question",
            low_confidence=True,
        )
        result.reply_text = dialog.say("unclear", lang)
        payload = result.to_dict()
        payload["asr_confidence"] = transcript.confidence
        payload["audio_seconds"] = transcript.duration_s
        payload["reply_audio_url"] = _speak(result.reply_text, lang)
        clock.lap("tts")
        payload["timings"] = clock.total()
        _cleanup(audio_path)
        return payload

    # ------------------------------------------------------------- dialog
    result = dialog.handle(user=user, text=transcript.text, language=lang, pending=pending)
    clock.lap("nlu")

    payload = result.to_dict()
    payload["asr_confidence"] = transcript.confidence
    payload["audio_seconds"] = transcript.duration_s

    # ---------------------------------------------------------------- TTS
    payload["reply_audio_url"] = _speak(result.reply_text, result.language)
    clock.lap("tts")

    payload["timings"] = clock.total()
    logger.info(
        "voice/query %s -> %s (%s) in %dms",
        user_id, result.intent, result.nlu_backend, payload["timings"]["total_ms"],
    )
    _cleanup(audio_path)
    return payload


def _speak(text: str, language: str) -> str | None:
    """Render the reply, or return None so the client uses the browser voice."""
    if not text:
        return None
    rel = get_tts().synthesize(text, language)
    return f"{settings.MEDIA_URL}{rel}" if rel else None


def _cleanup(audio_path: str) -> None:
    """Uploaded speech is deleted the moment it has been transcribed.

    A recording of someone saying their payee's name and an amount is personal
    data with no further use once the text exists. Keeping it would be a
    liability with no benefit, so the file's lifetime is one task.
    """
    try:
        Path(audio_path).unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not delete uploaded audio %s", audio_path)
