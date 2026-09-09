# -*- coding: utf-8 -*-
"""Speech recognition: faster-whisper, loaded once per process.

Three decisions worth defending in the report:

**The model is a module-level singleton.** Whisper-small is ~500 MB of weights
and several seconds of load time. Loading it per request would make the first
word of every sentence cost more than the sentence. The adapter loads lazily on
first use and holds the handle for the life of the worker, which is why heavy
work belongs in a Celery worker rather than a web worker.

**The language is forced, never detected.** The user picked their language on the
first screen, so we already know it. Passing ``language=`` to Whisper roughly
halves Tamil and Telugu error rates versus auto-detect, which frequently mistakes
short Tamil utterances for Malayalam or Kannada. Auto-detect runs only when we
genuinely have no preference on file.

**No system ffmpeg.** The browser hands us webm/opus from MediaRecorder.
faster-whisper decodes it through PyAV, which bundles its own FFmpeg libraries,
so a demo machine needs no PATH surgery and the Docker image needs no apt-get.
Decoding to 16 kHz mono is what Whisper wants anyway; PyAV resamples in passing.

Confidence is derived from the segment log-probabilities Whisper already reports,
and is used for exactly one thing: deciding when to stop guessing and hand the
user the icon grid instead (see ASR_MIN_CONFIDENCE).
"""
from __future__ import annotations

import logging
import math
import time

from django.conf import settings

from ..base import ASRAdapter, Transcript

logger = logging.getLogger(__name__)

# Whisper's own language codes for the four we support. Identical today, but the
# mapping is explicit so adding e.g. Bhojpuri (-> "hi") does not need a code hunt.
WHISPER_LANG = {"hi": "hi", "en": "en", "ta": "ta", "te": "te"}


def _resolve_device(requested: str) -> tuple[str, str]:
    """Return (device, compute_type). 'auto' picks CUDA when torch can see it.

    Compute type has to follow the device: int8_float16 is a CUDA-only
    quantisation that fails outright on CPU, so the CPU path is pinned to int8.
    The deployed CPU-only build therefore runs identical code at a different --
    and honestly reported -- latency.
    """
    device = requested
    if requested == "auto":
        try:
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"

    compute = settings.ASR_COMPUTE_TYPE
    if device == "cpu" and compute not in {"int8", "float32"}:
        compute = "int8"
    return device, compute


def _confidence(segments: list) -> float:
    """Collapse per-segment average log-probability into one 0-1 number.

    Whisper reports ``avg_logprob`` per segment (around -0.1 for a clean
    utterance, below -1.0 for noise). Weighting by duration stops a half-second
    cough at the end from dominating a five-second sentence.
    """
    if not segments:
        return 0.0
    total = 0.0
    total_weight = 0.0
    for seg in segments:
        weight = max(seg.end - seg.start, 0.05)
        total += math.exp(seg.avg_logprob) * weight
        total_weight += weight
    return round(min(total / total_weight, 1.0), 4) if total_weight else 0.0


class LocalWhisperASR(ASRAdapter):
    """faster-whisper behind the ASRAdapter interface."""

    name = "faster_whisper"

    def __init__(self) -> None:
        self._model = None
        self._load_attempted = False
        self._device = "cpu"

    @property
    def ready(self) -> bool:
        return self._model is not None

    def _load(self) -> None:
        if self._load_attempted:
            return
        self._load_attempted = True

        try:
            from faster_whisper import WhisperModel
        except ImportError:
            logger.warning(
                "faster-whisper is not installed -- audio transcription is "
                "unavailable. The typed / browser-ASR path at /api/voice/text/ "
                "still works. Install with: pip install faster-whisper"
            )
            return

        device, compute = _resolve_device(settings.ASR_DEVICE)
        started = time.perf_counter()
        try:
            self._model = WhisperModel(
                settings.ASR_MODEL_SIZE, device=device, compute_type=compute
            )
            self._device = device
            logger.info(
                "Loaded faster-whisper '%s' on %s (%s) in %.1fs",
                settings.ASR_MODEL_SIZE, device, compute, time.perf_counter() - started,
            )
        except Exception:
            logger.exception("Could not load faster-whisper '%s'", settings.ASR_MODEL_SIZE)

    def transcribe(self, audio_path: str, language: str | None = None) -> Transcript:
        self._load()
        if self._model is None:
            return Transcript(text="", language=language or "", confidence=0.0)

        started = time.perf_counter()
        segments, info = self._model.transcribe(
            audio_path,
            language=WHISPER_LANG.get(language or ""),
            beam_size=5,
            # Whisper hallucinates fluent sentences out of silence and room tone;
            # the VAD filter removes the silence before it can. A cheap phone mic
            # in a noisy village street is exactly what provokes this.
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 400},
            # Without this, a repeated word ("bhejo bhejo bhejo") can put the
            # decoder in a loop that fills the rest of the clip.
            condition_on_previous_text=False,
        )
        collected = list(segments)
        text = " ".join(seg.text.strip() for seg in collected).strip()

        elapsed = time.perf_counter() - started
        logger.info(
            "ASR %.2fs of audio in %.2fs (%s, %s) -> %r",
            info.duration, elapsed, info.language, self._device, text[:60],
        )
        return Transcript(
            text=text,
            language=language or info.language,
            confidence=_confidence(collected),
            duration_s=round(info.duration, 2),
        )
