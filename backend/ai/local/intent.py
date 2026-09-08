# -*- coding: utf-8 -*-
"""Intent classification: fine-tuned MuRIL, with a keyword baseline fallback.

Two implementations behind one adapter:

* ``LocalIntentClassifier`` loads the model trained by ml/train_intent.py.
* ``KeywordIntentBaseline`` needs no model at all.

The baseline is not a placeholder to be deleted. It is (a) the ablation row the
report compares the trained model against, and (b) the reason the app still
functions if the artifact is missing on demo day or on a machine without torch.
The classifier falls back to it automatically and logs loudly when it does.
"""
from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings

from ..base import IntentPrediction, NLUAdapter
from .slots import extract_amount, extract_payee, normalize

logger = logging.getLogger(__name__)

# Keyword cues per intent, across all four languages plus transliteration.
KEYWORD_CUES: dict[str, list[str]] = {
    "send_money": [
        "भेज", "ट्रांसफर", "पेमेंट", "चुका", "डाल दो", "देने ह", "भुगतान", "पहुचा", "पहुँचा",
        "bhej", "transfer", "send", "pay ", "payment", "remit", "dena hai",
        "அனுப்ப", "செலுத்த", "கொடுத்து", "மாற்று", "கட்டு",
        "పంపు", "పంపించు", "చెల్లించు", "బదిలీ", "వేసేయ్", "జమ", "కట్టేయ్",
    ],
    "check_balance": [
        "बैलेंस", "कितने पैसे", "कितना पैसा", "खाते में कितन", "जमा पूंजी", "कितना बचा",
        "balance", "how much money", "how much i have", "funds", "kitna paisa", "kitne paise",
        "இருப்பு", "பேலன்ஸ்", "எவ்வளவு பணம்", "எவ்வளவு மிச்சம்", "கணக்கு காலி",
        "బ్యాలెన్స్", "ఎంత డబ్బు", "ఎంత మిగిలింది", "ఖాతా ఖాళీ",
    ],
    "transaction_history": [
        "लेनदेन", "स्टेटमेंट", "पिछले पेमेंट", "इतिहास", "हिसाब", "खर्चे", "किसको भेजा",
        "transaction", "statement", "history", "recent activity", "spent this",
        "who received", "last payment", "hisaab",
        "பரிவர்த்தனை", "அறிக்கை", "செலவழித்த", "யாருக்கு பணம்", "பழைய கணக்",
        "లావాదేవీ", "స్టేట్‌మెంట్", "ఖర్చు చేసిన", "ఎవరికి డబ్బు", "పాత లెక్క",
    ],
    "check_eligibility": [
        "योग्य", "पात्र", "मिल सकता", "शर्तें", "अर्ह",
        "eligible", "qualify", "do i get", "can i get", "conditions for", "apply for this",
        "தகுதி", "கிடைக்குமா", "விண்ணப்பிக்க",
        "అర్హ", "వస్తుందా", "దరఖాస్తు",
    ],
    "find_scheme": [
        "योजना", "स्कीम", "सरकारी", "सरकार से", "सब्सिडी", "अनुदान",
        "scheme", "government", "subsidy", "yojana", "sarkari", "welfare",
        "திட்டம்", "அரசு", "உதவித்தொகை",
        "పథకం", "ప్రభుత్వ", "సబ్సిడీ",
    ],
    "scan_qr": [
        "क्यूआर", "कोड स्कैन", "स्कैन", "चौकोर कोड", "कोड देखो", "कोड पढ़",
        "qr", "scan", "square code", "read the code", "sticker code",
        "க்யூஆர்", "ஸ்கேன்", "கோடை", "சதுர கோடு",
        "క్యూఆర్", "స్కాన్", "కోడ్",
    ],
    "identify_note": [
        "नोट", "कितने का", "कागज है", "गुलाबी वाला", "नोट की कीमत",
        "note", "denomination", "currency", "paper money", "which rupee",
        "நோட்டு", "தாள்", "பணத்தை சொல்",
        "నోటు", "కాగితం", "డబ్బు చెప్పు",
    ],
    "report_scam": [
        "धोखा हुआ", "ठगा", "चुरा", "शिकायत", "पैसे गायब", "खाली कर दिया", "ले गया",
        "scammed", "stole", "report a fraud", "file a complaint", "cheat", "emptied my account",
        "ஏமாற்ற", "திருடி", "புகார்", "பணம் போய்",
        "మోసపోయా", "దొంగిలించ", "ఫిర్యాదు", "డబ్బు పోయింది",
    ],
    "check_scam": [
        "सही है क्या", "असली है", "फ्रॉड तो नहीं", "लिंक सुरक्षित", "ओटीपी मांग",
        "मैसेज चेक", "लॉटरी", "केवाईसी", "धोखेबाज है",
        "is this genuine", "is this a scam", "is this safe", "asking for my otp",
        "should i believe", "should i open", "verify this message", "lottery", "kyc",
        "உண்மையா", "மோசடி", "பாதுகாப்பான", "ஓடிபி", "லாட்டரி", "நம்பலாமா",
        "నిజమైనదా", "మోసపు", "సురక్షిత", "ఓటీపీ", "లాటరీ", "నమ్మాలా",
    ],
    "learn_topic": [
        "क्या होता है", "समझा", "सीख", "सिखाओ", "कैसे काम करता",
        "what is", "explain", "teach me", "how does", "learn about", "samjhao", "sikha",
        "என்றால் என்ன", "விளக்க", "கற்று",
        "అంటే ఏమిటి", "వివరించు", "నేర్పు",
    ],
    "set_language": [
        "भाषा", "में बात करो", "में बोलो", "में जवाब",
        "language", "speak in", "switch to", "answer me in", "talk to me in", "bhasha",
        "மொழி", "இல் பேசு", "தமிழில்", "மாத்து",
        "భాష", "లో మాట్లాడు", "తెలుగులో", "మార్చు",
    ],
    "repeat": [
        "फिर से", "दोबारा", "सुना नहीं", "आवाज", "एक बार और", "क्या कहा",
        "say that again", "repeat", "did not hear", "one more time", "missed that", "come again",
        "மீண்டும்", "திரும்ப", "கேட்கல", "இன்னொரு தடவை",
        "మళ్లీ", "మరోసారి", "వినలేదు", "ఇంకోసారి",
    ],
    "help": [
        "मदद", "समझ नहीं आ", "कैसे चलाए", "कैसे इस्तेमाल", "क्या क्या कर",
        "नया हूं", "option", "guide",
        "help", "guide me", "what can you do", "how do i use", "i am new", "confused",
        "உதவி", "புரியல", "எப்படி பயன்படுத்த", "வழிகாட்ட", "புதுசு",
        "సహాయం", "అర్థం కావట్లేదు", "ఎలా వాడాలి", "దారి చూపించు", "కొత్త",
    ],
}


class KeywordIntentBaseline(NLUAdapter):
    """Substring-cue classifier. No model, no torch, no artifacts."""

    name = "keyword_baseline"

    def predict(self, text: str, language: str = "hi") -> IntentPrediction:
        haystack = normalize(text).lower()

        scores: dict[str, float] = {}
        for intent, cues in KEYWORD_CUES.items():
            hits = [cue for cue in cues if cue.strip() and cue.strip() in haystack]
            if hits:
                # Longer cues are more distinctive than short ones.
                scores[intent] = sum(len(cue.strip()) for cue in hits) / 10.0

        # A money verb combined with an amount is decisive.
        amount = extract_amount(text)
        if amount is not None and "send_money" in scores:
            scores["send_money"] += 3.0

        if not scores:
            return IntentPrediction(intent="unknown", confidence=0.30, slots={})

        best = max(scores, key=scores.get)
        total = sum(scores.values())
        confidence = min(0.88, 0.45 + scores[best] / max(total, 1e-6) * 0.45)
        return IntentPrediction(
            intent=best,
            confidence=round(confidence, 3),
            slots={},
            all_scores={k: round(v, 3) for k, v in scores.items()},
        )


class LocalIntentClassifier(NLUAdapter):
    """Fine-tuned MuRIL, loaded once per process, with automatic fallback."""

    name = "muril_intent"

    def __init__(self) -> None:
        self._ready = False
        self._fallback = KeywordIntentBaseline()
        self._load_attempted = False

    @property
    def active_backend(self) -> str:
        """Which implementation actually answered. Surfaced in the API response
        so a demo never silently reports baseline numbers as model numbers."""
        return self.name if self._ready else self._fallback.name

    def _load(self) -> None:
        if self._load_attempted:
            return
        self._load_attempted = True

        model_dir = Path(settings.INTENT_MODEL_PATH)
        if not (model_dir / "config.json").exists():
            logger.warning(
                "Intent model not found at %s -- falling back to the keyword "
                "baseline. Run: python ml/train_intent.py",
                model_dir,
            )
            return

        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            self._torch = torch
            self._tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
            self._model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
            self._model.eval()
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model.to(self._device)
            self._id2label = self._model.config.id2label
            self._ready = True
            logger.info("Loaded intent model from %s on %s", model_dir, self._device)
        except Exception:
            logger.exception("Failed to load the intent model; using the keyword baseline")

    def predict(self, text: str, language: str = "hi") -> IntentPrediction:
        self._load()
        if not self._ready:
            return self._fallback.predict(text, language)

        torch = self._torch
        inputs = self._tokenizer(
            normalize(text), return_tensors="pt", truncation=True, max_length=64
        ).to(self._device)
        with torch.no_grad():
            logits = self._model(**inputs).logits[0]
        probs = torch.softmax(logits, dim=-1)
        top = int(torch.argmax(probs))
        return IntentPrediction(
            intent=self._id2label[top],
            confidence=round(float(probs[top]), 4),
            slots={},
            all_scores={
                self._id2label[i]: round(float(p), 4) for i, p in enumerate(probs.tolist())
            },
        )


def fill_slots(text: str, intent: str, contacts: list[dict] | None = None) -> dict:
    """Attach the slots an intent needs. Kept separate from classification so the
    trained model and the baseline share exactly one slot implementation."""
    slots: dict = {}
    if intent == "send_money":
        slots["amount"] = extract_amount(text)
        slots["payee"] = extract_payee(text, contacts or [])
    elif intent in {"learn_topic", "find_scheme", "check_eligibility"}:
        slots["query"] = text
    elif intent == "set_language":
        slots["language"] = detect_requested_language(text)
    return slots


_LANGUAGE_CUES = {
    "hi": ["हिंदी", "हिन्दी", "hindi"],
    "en": ["अंग्रेजी", "english", "angrezi", "ஆங்கில", "ఇంగ్లీష"],
    "ta": ["तमिल", "tamil", "தமிழ", "తమిళ"],
    "te": ["तेलुगु", "telugu", "తెలుగు", "தெலுங்"],
}


def detect_requested_language(text: str) -> str | None:
    haystack = normalize(text).lower()
    for code, cues in _LANGUAGE_CUES.items():
        if any(cue in haystack for cue in cues):
            return code
    return None
