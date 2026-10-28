# -*- coding: utf-8 -*-
"""ScamNet at serving time: fine-tuned MuRIL blended with rule features.

    p = w * p_transformer + (1 - w) * p_rules        (3-class probabilities)
    label = argmax(p);  score = p[scam] + 0.5 * p[suspicious]

The transformer decides; the rules explain. Every reason the user hears comes
from a rule feature that actually fired on their message, so a reason can never
be a hallucinated justification for a number -- it is a property of the text
they can check with their own eyes.

Degrades in two steps. No transformer artifact -> rules only (logged loudly).
No fitted rules.json either -> the hand-set DEFAULT_WEIGHTS. The endpoint keeps
answering in every case and says which backend answered.
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

import numpy as np
from django.conf import settings

from ..base import ScamAdapter, ScamVerdict
from . import scam_rules

logger = logging.getLogger(__name__)

CLASSES = ["safe", "suspicious", "scam"]

ADVICE = {
    "scam": {
        "hi": "जवाब मत दीजिए, लिंक मत खोलिए, कोई पैसा मत भेजिए। ठगी की शिकायत 1930 पर कीजिए।",
        "en": "Do not reply, do not open the link, do not pay anything. Report fraud on 1930.",
        "ta": "பதில் அனுப்பாதீர்கள், இணைப்பைத் திறக்காதீர்கள், பணம் அனுப்பாதீர்கள். மோசடியை 1930-ல் புகார் செய்யுங்கள்.",
        "te": "జవాబు ఇవ్వకండి, లింక్ తెరవకండి, డబ్బు పంపకండి. మోసాన్ని 1930కి ఫిర్యాదు చేయండి.",
    },
    "suspicious": {
        "hi": "सावधान रहिए। कोई जानकारी मत दीजिए। सीधे अपने बैंक से पूछिए।",
        "en": "Be careful. Do not share any details. Check directly with your bank.",
        "ta": "கவனமாக இருங்கள். எந்த விவரமும் தராதீர்கள். நேரடியாக உங்கள் வங்கியிடம் கேளுங்கள்.",
        "te": "జాగ్రత్తగా ఉండండి. ఏ వివరాలూ ఇవ్వకండి. నేరుగా మీ బ్యాంకును అడగండి.",
    },
    "safe": {
        "hi": "यह संदेश सामान्य लगता है। फिर भी अपना OTP या PIN कभी किसी को मत बताइए।",
        "en": "This message looks normal. Even so, never share your OTP or PIN with anyone.",
        "ta": "இந்தச் செய்தி சாதாரணமாகத் தெரிகிறது. இருந்தாலும் உங்கள் OTP, PIN-ஐ யாரிடமும் சொல்லாதீர்கள்.",
        "te": "ఈ సందేశం సాధారణంగా ఉంది. అయినా మీ OTP, PIN ఎవరికీ చెప్పకండి.",
    },
}

HEADLINE = {
    "scam": {"hi": "यह ठगी है", "en": "This is a scam", "ta": "இது மோசடி", "te": "ఇది మోసం"},
    "suspicious": {"hi": "यह संदेह वाला है", "en": "This looks suspicious",
                   "ta": "இது சந்தேகத்திற்குரியது", "te": "ఇది అనుమానాస్పదంగా ఉంది"},
    "safe": {"hi": "यह सुरक्षित लगता है", "en": "This looks safe",
             "ta": "இது பாதுகாப்பானதாகத் தெரிகிறது", "te": "ఇది సురక్షితంగా ఉంది"},
}

# When the transformer flags a message but no rule fired, there is still one
# honest thing to say: it reads like known fraud. Better than an unexplained red.
WORDING_REASON = {
    "hi": "इसकी भाषा जानी-पहचानी ठगी वाले संदेशों जैसी है।",
    "en": "The wording matches messages that are commonly used for fraud.",
    "ta": "இதன் சொற்கள் வழக்கமான மோசடிச் செய்திகளைப் போல உள்ளன.",
    "te": "దీని భాష సాధారణ మోసపు సందేశాల లాగా ఉంది.",
}
DISCLAIMER_REASON = {
    "hi": "संदेश खुद कहता है कि OTP किसी को न बताएं — असली बैंक ऐसा ही लिखते हैं।",
    "en": "The message itself tells you not to share the OTP, which is what genuine banks write.",
    "ta": "OTP-ஐப் பகிர வேண்டாம் என்று செய்தியே சொல்கிறது; உண்மையான வங்கிகள் இப்படித்தான் எழுதுகின்றன.",
    "te": "OTP పంచుకోవద్దని సందేశమే చెబుతోంది; నిజమైన బ్యాంకులు ఇలాగే రాస్తాయి.",
}


class LocalScamDetector(ScamAdapter):
    name = "scamnet"

    def __init__(self, model_dir: str | None = None):
        self.model_dir = Path(model_dir or settings.SCAM_MODEL_PATH)
        self.weight = float(getattr(settings, "SCAM_MODEL_WEIGHT", 0.7))
        self._lock = threading.Lock()
        self._loaded = False
        self._model = self._tokenizer = self._device = None
        self._rules = None

    # ------------------------------------------------------------ loading
    def _load(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            rules_path = self.model_dir / "rules.json"
            if rules_path.exists():
                self._rules = json.loads(rules_path.read_text(encoding="utf-8"))
            if (self.model_dir / "config.json").exists():
                try:
                    import torch
                    from transformers import AutoModelForSequenceClassification, AutoTokenizer

                    self._device = "cuda" if torch.cuda.is_available() else "cpu"
                    self._tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir))
                    self._model = AutoModelForSequenceClassification.from_pretrained(
                        str(self.model_dir)).to(self._device).eval()
                    logger.info("ScamNet loaded from %s on %s", self.model_dir, self._device)
                except Exception:  # noqa: BLE001
                    logger.exception("ScamNet transformer failed to load; rules only")
            else:
                logger.warning("No ScamNet artifact at %s; rules only", self.model_dir)
            self._loaded = True

    @property
    def active_backend(self) -> str:
        self._load()
        if self._model is not None:
            return "scamnet_blend"
        return "rules_fitted" if self._rules else "rules_default"

    # ------------------------------------------------------------ halves
    def _rules_proba(self, text: str) -> np.ndarray:
        feats = scam_rules.extract(text)
        if self._rules:
            x = np.array([feats[f] for f in self._rules["features"]])
            z = np.array(self._rules["coef"]) @ x + np.array(self._rules["intercept"])
            z -= z.max()
            e = np.exp(z)
            return e / e.sum()
        # No fitted model: split the binary risk evenly between the two "not safe"
        # classes rather than inventing a distinction the rules cannot make.
        risk = scam_rules.score(text).risk
        return np.array([1 - risk, risk / 2, risk / 2])

    def _model_proba(self, text: str) -> np.ndarray | None:
        if self._model is None:
            return None
        import torch

        with torch.no_grad():
            enc = self._tokenizer([text], return_tensors="pt", truncation=True,
                                  max_length=128).to(self._device)
            return torch.softmax(self._model(**enc).logits, dim=-1)[0].cpu().numpy()

    # ------------------------------------------------------------ public
    def classify(self, text: str, language: str = "hi") -> ScamVerdict:
        self._load()
        lang = language if language in scam_rules.LANGS else "en"
        p_rules = self._rules_proba(text)
        p_model = self._model_proba(text)
        p = p_rules if p_model is None else self.weight * p_model + (1 - self.weight) * p_rules

        label = CLASSES[int(np.argmax(p))]
        score = float(p[2] + 0.5 * p[1])

        weights = (self._rules or {}).get("toward_scam") or scam_rules.DEFAULT_WEIGHTS
        rule_result = scam_rules.score(text, weights=weights, bias=0.0)
        reasons = rule_result.reasons(lang)[:3] if label != "safe" else []
        if label != "safe" and not reasons:
            reasons = [WORDING_REASON[lang]]
        if label == "safe" and rule_result.features.get("has_disclaimer"):
            reasons = [DISCLAIMER_REASON[lang]]

        return ScamVerdict(
            label=label,
            score=round(score, 4),
            reasons=reasons,
            model_score=round(float(p_model[2] + 0.5 * p_model[1]), 4) if p_model is not None else 0.0,
            rule_score=round(float(p_rules[2] + 0.5 * p_rules[1]), 4),
        )

    def explain(self, verdict: ScamVerdict, language: str) -> dict:
        lang = language if language in scam_rules.LANGS else "en"
        return {"headline": HEADLINE[verdict.label][lang], "advice": ADVICE[verdict.label][lang]}
