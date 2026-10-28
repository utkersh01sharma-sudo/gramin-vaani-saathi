"""HTTP clients for the model server (backend/ai/server.py).

Each class implements the same interface as its local counterpart, so nothing
above the registry knows or cares which one it got. That is the whole point of
the adapter layer: AI_BACKEND=remote is a settings change, not a code change.

Failure policy matches the local adapters -- degrade, never break:
  * NLU unreachable  -> the keyword baseline, so voice still navigates
  * scam unreachable -> the pure-Python rule layer, so checks still explain
  * ASR unreachable  -> an error; there is no honest fallback for transcription,
    and the client's own text box already is the fallback
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from pathlib import Path

from django.conf import settings

from ..base import (ASRAdapter, IntentPrediction, NLUAdapter, ScamAdapter, ScamVerdict,
                    Transcript)

logger = logging.getLogger(__name__)


class RemoteError(RuntimeError):
    pass


def _post(path: str, body: bytes, content_type: str, extra_headers: dict | None = None,
          timeout: float | None = None) -> dict:
    url = settings.AI_REMOTE_URL.rstrip("/") + path
    headers = {"Content-Type": content_type, **(extra_headers or {})}
    key = getattr(settings, "AI_REMOTE_KEY", "")
    if key:
        headers["X-Model-Key"] = key
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout or settings.AI_REMOTE_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RemoteError(f"{url}: {exc}") from exc


def _post_json(path: str, payload: dict) -> dict:
    return _post(path, json.dumps(payload).encode("utf-8"), "application/json")


class RemoteNLU(NLUAdapter):
    name = "remote"

    def __init__(self):
        self.active_backend = "remote"

    def predict(self, text: str, language: str = "hi") -> IntentPrediction:
        try:
            data = _post_json("/v1/nlu", {"text": text, "language": language})
            self.active_backend = f"remote:{data.get('backend', '?')}"
            return IntentPrediction(intent=data["intent"], confidence=data["confidence"],
                                    slots=data.get("slots") or {},
                                    all_scores=data.get("all_scores") or {})
        except RemoteError:
            logger.exception("model server unreachable; keyword baseline")
            from ..local.intent import KeywordIntentBaseline

            self.active_backend = "keyword_baseline(remote down)"
            return KeywordIntentBaseline().predict(text, language)


class RemoteScam(ScamAdapter):
    name = "remote"

    def __init__(self):
        self.active_backend = "remote"

    def classify(self, text: str, language: str = "hi") -> ScamVerdict:
        try:
            data = _post_json("/v1/scam", {"text": text, "language": language})
            self.active_backend = f"remote:{data.get('backend', '?')}"
            return ScamVerdict(label=data["label"], score=data["score"], reasons=data.get("reasons", []),
                               model_score=data.get("model_score", 0.0),
                               rule_score=data.get("rule_score", 0.0))
        except RemoteError:
            logger.exception("model server unreachable; rule layer only")
            from ..local.scam import LocalScamDetector

            self.active_backend = "rules_default(remote down)"
            # A directory with no artifacts: the detector falls back to the
            # pure-Python rules, which need nothing from the model server.
            return LocalScamDetector(model_dir="/nonexistent").classify(text, language)

    def explain(self, verdict: ScamVerdict, language: str) -> dict:
        # Headline and advice are fixed sentences keyed by label, not model
        # output, so they are read locally. Keeping no per-request state on the
        # adapter also keeps it safe to share between threads.
        from ..local.scam import ADVICE, HEADLINE

        lang = language if language in HEADLINE["scam"] else "en"
        return {"headline": HEADLINE[verdict.label][lang], "advice": ADVICE[verdict.label][lang]}


class RemoteASR(ASRAdapter):
    name = "remote"

    def transcribe(self, audio_path: str, language: str | None = None) -> Transcript:
        path = Path(audio_path)
        headers = {"X-Filename": path.name}
        if language:
            headers["X-Language"] = language
        data = _post("/v1/asr", path.read_bytes(), "application/octet-stream", headers,
                     timeout=max(settings.AI_REMOTE_TIMEOUT, 30))
        return Transcript(text=data["text"], language=data["language"],
                          confidence=data["confidence"], duration_s=data.get("duration_s", 0.0))
