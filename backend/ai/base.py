"""Adapter interfaces for every model the app uses.

Views and Celery tasks depend only on these dataclasses and protocols -- never on
transformers, faster-whisper, or cv2 directly. That indirection is what lets the
same code run two ways:

    AI_BACKEND=local   models load in-process (dev laptop, single-box demo)
    AI_BACKEND=remote  identical calls go over HTTP to a dedicated model server

Scaling out therefore costs one environment variable, not a rewrite.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Transcript:
    text: str
    language: str
    confidence: float
    duration_s: float = 0.0


@dataclass
class IntentPrediction:
    intent: str
    confidence: float
    slots: dict = field(default_factory=dict)
    all_scores: dict = field(default_factory=dict)


@dataclass
class ScamVerdict:
    """``label`` is one of safe / suspicious / scam.

    ``reasons`` is mandatory, not decorative: a non-literate user cannot audit a
    number, so every verdict must be explainable in one spoken sentence.
    """

    label: str
    score: float
    reasons: list[str] = field(default_factory=list)
    model_score: float = 0.0
    rule_score: float = 0.0


@dataclass
class NotePrediction:
    denomination: int | None
    confidence: float
    is_note: bool = True


@dataclass
class QRResult:
    raw: str = ""
    payee_vpa: str = ""
    payee_name: str = ""
    amount: float | None = None
    is_valid_upi: bool = False
    tamper_score: float = 0.0
    warnings: list[str] = field(default_factory=list)


class ASRAdapter(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str, language: str | None = None) -> Transcript: ...


class TTSAdapter(ABC):
    @abstractmethod
    def synthesize(self, text: str, language: str) -> str:
        """Return a MEDIA_ROOT-relative path to the rendered audio file."""


class NLUAdapter(ABC):
    @abstractmethod
    def predict(self, text: str, language: str = "hi") -> IntentPrediction: ...


class ScamAdapter(ABC):
    @abstractmethod
    def classify(self, text: str, language: str = "hi") -> ScamVerdict: ...


class VisionAdapter(ABC):
    @abstractmethod
    def read_qr(self, image_path: str) -> QRResult: ...

    @abstractmethod
    def identify_note(self, image_path: str) -> NotePrediction: ...
