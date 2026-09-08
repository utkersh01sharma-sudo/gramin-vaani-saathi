"""Settings-driven factory for the AI adapters.

Adapters are cached per-process, so a Celery worker loads Whisper once at first
use and reuses it for every subsequent task instead of paying the load cost per
request.
"""
from __future__ import annotations

from functools import lru_cache

from django.conf import settings

from . import base


def _backend() -> str:
    return getattr(settings, "AI_BACKEND", "local")


@lru_cache(maxsize=1)
def get_asr() -> base.ASRAdapter:
    if _backend() == "remote":
        from .remote.client import RemoteASR

        return RemoteASR()
    from .local.asr import LocalWhisperASR

    return LocalWhisperASR()


@lru_cache(maxsize=1)
def get_tts() -> base.TTSAdapter:
    from .local.tts import GttsTTS

    return GttsTTS()


@lru_cache(maxsize=1)
def get_nlu() -> base.NLUAdapter:
    if _backend() == "remote":
        from .remote.client import RemoteNLU

        return RemoteNLU()
    from .local.intent import LocalIntentClassifier

    return LocalIntentClassifier()


@lru_cache(maxsize=1)
def get_scam() -> base.ScamAdapter:
    if _backend() == "remote":
        from .remote.client import RemoteScam

        return RemoteScam()
    from .local.scam import LocalScamDetector

    return LocalScamDetector()


@lru_cache(maxsize=1)
def get_vision() -> base.VisionAdapter:
    from .local.vision import LocalVision

    return LocalVision()
