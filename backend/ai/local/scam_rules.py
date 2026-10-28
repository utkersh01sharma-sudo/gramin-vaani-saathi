# -*- coding: utf-8 -*-
"""Hand-engineered scam signals, each with a reason a person can act on.

This module is the explainable half of ScamNet. The transformer reads phrasing;
these read *mechanics* -- a link, a shortened link, a request for an OTP, a fee
to receive a prize. A transformer score alone tells a non-literate user nothing
they can check; "this message asks for your OTP, and no bank ever does" is
something they can hold the next message up against.

Pure Python, no Django and no torch, because the same function runs in three
places and must give the same answer in all of them: ml/train_scam.py fits the
rule-only model on it, the ablation scores it, and the API calls it per request.

A feature is a (name, detector, weight hint, reasons) tuple. The weights that
are actually used come from a logistic regression fitted on the training set
(ml/artifacts/scam/rules.json); ``DEFAULT_WEIGHTS`` is only the fallback when
that file is missing, and is deliberately conservative.
"""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass

LANGS = ("hi", "en", "ta", "te")

# ---------------------------------------------------------------- lexicons
SECRET = [
    "otp", "o.t.p", "pin", "cvv", "password", "upi pin", "mpin", "atm pin", "card number",
    "ओटीपी", "पिन", "पासवर्ड", "सीवीवी", "कार्ड नंबर",
    "ஓடிபி", "பின்", "கடவுச்சொல்", "கார்டு எண்",
    "ఓటీపీ", "పిన్", "పాస్‌వర్డ్", "కార్డు నంబర్",
]
SHARE_VERBS = [
    "share", "send", "tell", "give", "reply with", "forward", "provide", "enter",
    "bhejo", "bhej do", "batao", "bata do", "bataiye", "dijiye", "do na",
    "भेजें", "भेजो", "भेज दो", "बताएं", "बताओ", "बताइए", "दीजिए", "दे दो", "शेयर",
    "அனுப்பு", "அனுப்புங்கள்", "சொல்லுங்கள்", "சொல்லு", "கொடுங்கள்", "பகிருங்கள்",
    "పంపండి", "పంపు", "చెప్పండి", "చెప్పు", "ఇవ్వండి", "షేర్ చేయండి",
]
# The single most important negative signal. A genuine bank OTP message *also*
# mentions the OTP -- it is the disclaimer that tells them apart.
DISCLAIMER = [
    "do not share", "don't share", "never share", "never ask", "will never ask", "not share",
    "kisi ko na", "kisi ko mat", "share na kare", "share mat",
    "किसी को न", "किसी के साथ साझा न", "शेयर न करें", "कभी नहीं माँगता", "कभी नहीं मांगता",
    "யாரிடமும் பகிர வேண்டாம்", "பகிர வேண்டாம்", "ஒருபோதும் கேட்காது",
    "ఎవరితోనూ పంచుకోవద్దు", "పంచుకోవద్దు", "ఎప్పుడూ అడగదు", "ఎవరికీ చెప్పవద్దు",
]
URGENCY = [
    "urgent", "immediately", "within 24", "today only", "last chance", "act now", "expire",
    "expires today", "right now", "hurry",
    "turant", "abhi", "jaldi", "aaj hi", "warna",
    "तुरंत", "अभी", "जल्दी", "आज ही", "वरना", "24 घंटे", "अंतिम",
    "உடனே", "உடனடியாக", "இன்றே", "24 மணி", "இல்லையெனில்",
    "వెంటనే", "ఇప్పుడే", "ఈరోజే", "24 గంటల", "లేకపోతే",
]
THREAT = [
    "blocked", "block", "suspend", "suspended", "deactivat", "freeze", "frozen", "kyc expired",
    "kyc pending", "kyc update", "disconnect", "cut off", "legal action", "arrest", "police case",
    "band ho", "block ho", "kat jayegi",
    "बंद हो", "ब्लॉक", "निलंबित", "केवाईसी", "कट जाएगी", "काट दी जाएगी", "कानूनी कार्रवाई", "गिरफ्तार",
    "முடக்கப்", "நிறுத்தப்படும்", "கேஒய்சி", "துண்டிக்கப்படும்", "சட்ட நடவடிக்கை", "கைது",
    "బ్లాక్", "నిలిపివేయ", "కేవైసీ", "కట్ చేయ", "చట్టపరమైన చర్య", "అరెస్ట్",
]
PRIZE = [
    "won", "winner", "lottery", "prize", "lucky draw", "jackpot", "reward", "gift voucher",
    "cashback of", "kbc", "selected for",
    "inaam", "jeet", "lottery lagi",
    "जीत", "लॉटरी", "इनाम", "पुरस्कार", "लकी ड्रा", "केबीसी", "उपहार",
    "வென்றீர்கள்", "லாட்டரி", "பரிசு", "அதிர்ஷ்ட",
    "గెలుచుకున్నారు", "లాటరీ", "బహుమతి", "లక్కీ డ్రా",
]
PAY_TO_RECEIVE = [
    "processing fee", "registration fee", "pay to receive", "to receive the", "to claim",
    "refundable deposit", "advance fee", "gst charge", "scan to receive", "enter pin to receive",
    "fees", "fee of",
    "फीस", "शुल्क", "पाने के लिए", "प्राप्त करने के लिए", "जमा करें",
    "கட்டணம்", "பெற", "பெறுவதற்கு",
    "రుసుము", "ఫీజు", "పొందడానికి", "అందుకోవడానికి",
]
REMOTE_APP = ["anydesk", "teamviewer", "quicksupport", "quick support", "screen share", "rustdesk",
              "एनीडेस्क", "டீம்வியூவர்", "ఎనీడెస్క్"]
JOB = ["work from home", "part time", "part-time", "earn daily", "per day", "like videos",
       "daily income", "ghar baithe", "घर बैठे", "रोज़ कमाएं", "प्रतिदिन", "வீட்டிலிருந்தே", "தினமும்",
       "ఇంటి నుండే", "రోజుకు"]
SHORTENERS = ["bit.ly", "tinyurl", "cutt.ly", "is.gd", "rb.gy", "goo.gl", "t.co/", "shorturl",
              "tiny.cc", "ow.ly"]
SAFE_DOMAINS = (".gov.in", ".nic.in", "sbi.co.in", "onlinesbi.sbi", ".bank.in", "irctc.co.in",
                "amazon.in", "npci.org.in", "rbi.org.in", "uidai.gov.in")
RISKY_TLDS = (".xyz", ".top", ".online", ".click", ".shop", ".site", ".info", ".live",
              ".in.net", ".buzz", ".work", ".loan", ".win")

URL_RE = re.compile(r"(https?://\S+|www\.\S+|\b[a-z0-9-]+(?:\.[a-z0-9-]+)+/\S*|\b[a-z0-9-]+\.(?:xyz|top|online|click|shop|site|info|live|buzz|work|loan|win|com|in|net|org)\b)", re.I)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")
TOLL_FREE_RE = re.compile(r"\b1800[\s-]?\d{3}[\s-]?\d{3,4}\b")
AMOUNT_RE = re.compile(r"(?:₹|rs\.?|inr|रु|रुपये|ரூ|రూ)\s?[\d,]{3,}", re.I)
ZERO_WIDTH = re.compile(r"[​‌‍⁠﻿]")


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower()


def _any(text: str, words: list[str]) -> bool:
    return any(w in text for w in words)


def _mixed_script_word(text: str) -> bool:
    """A Latin word with a Cyrillic or Greek letter inside it: 'pаytm' with a Cyrillic 'а'."""
    for word in re.findall(r"\w+", text):
        scripts = set()
        for ch in word:
            if ch.isascii() and ch.isalpha():
                scripts.add("latin")
            elif "Ѐ" <= ch <= "ӿ":
                scripts.add("cyrillic")
            elif "Ͱ" <= ch <= "Ͽ":
                scripts.add("greek")
        if "latin" in scripts and len(scripts) > 1:
            return True
    return False


# ---------------------------------------------------------------- features
def extract(text: str) -> dict[str, float]:
    """Binary features. Order is fixed by FEATURES below."""
    raw = text or ""
    t = _norm(raw)
    urls = URL_RE.findall(t)
    has_link = bool(urls)
    safe_link = has_link and all(any(d in u for d in SAFE_DOMAINS) for u in urls)

    mentions_secret = _any(t, SECRET)
    disclaimer = _any(t, DISCLAIMER)
    # A share verb within the same message as a secret word, *without* the
    # disclaimer. Crude, and the reason the transformer exists, but it is right
    # far more often than not.
    asks_secret = mentions_secret and _any(t, SHARE_VERBS) and not disclaimer

    phones = [p for p in PHONE_RE.findall(raw)]
    return {
        "asks_for_secret": float(asks_secret),
        "mentions_secret": float(mentions_secret),
        "has_disclaimer": float(disclaimer),
        "has_link": float(has_link and not safe_link),
        "short_link": float(_any(t, SHORTENERS)),
        "risky_domain": float(any(any(tld in u for tld in RISKY_TLDS) for u in urls)),
        "official_link": float(safe_link),
        "phone_number": float(bool(phones)),
        "toll_free": float(bool(TOLL_FREE_RE.search(raw))),
        "urgency": float(_any(t, URGENCY)),
        "threat": float(_any(t, THREAT)),
        "prize": float(_any(t, PRIZE)),
        "pay_to_receive": float(_any(t, PAY_TO_RECEIVE)),
        "remote_app": float(_any(t, REMOTE_APP)),
        "job_offer": float(_any(t, JOB)),
        "money_amount": float(bool(AMOUNT_RE.search(t))),
        "lookalike_chars": float(_mixed_script_word(raw) or bool(ZERO_WIDTH.search(raw))),
    }


FEATURES = list(extract("").keys())

# Features that never produce a reason: they lower risk, or they only matter in
# combination (a money amount on its own is every bank alert ever sent).
SILENT = {"mentions_secret", "has_disclaimer", "official_link", "toll_free", "money_amount"}

REASONS: dict[str, dict[str, str]] = {
    "asks_for_secret": {
        "hi": "यह संदेश आपका OTP या PIN माँग रहा है। कोई भी बैंक यह कभी नहीं माँगता।",
        "en": "This message asks for your OTP or PIN. No bank ever asks for these.",
        "ta": "இந்தச் செய்தி உங்கள் OTP அல்லது PIN-ஐக் கேட்கிறது. எந்த வங்கியும் இதைக் கேட்காது.",
        "te": "ఈ సందేశం మీ OTP లేదా PIN అడుగుతోంది. ఏ బ్యాంకూ ఇది ఎప్పుడూ అడగదు.",
    },
    "has_link": {
        "hi": "इसमें एक लिंक है जो किसी सरकारी या बैंक की वेबसाइट का नहीं है।",
        "en": "It contains a link that is not an official bank or government website.",
        "ta": "இதில் வங்கி அல்லது அரசு அல்லாத ஒரு இணைப்பு உள்ளது.",
        "te": "ఇందులో బ్యాంకు లేదా ప్రభుత్వానిది కాని లింక్ ఉంది.",
    },
    "short_link": {
        "hi": "लिंक छोटा करके छिपाया गया है, ताकि असली पता न दिखे।",
        "en": "The link is shortened, which hides where it really goes.",
        "ta": "இணைப்பு சுருக்கப்பட்டுள்ளது; அது உண்மையில் எங்கே போகிறது என்று தெரியாது.",
        "te": "లింక్ కుదించబడింది; అది నిజంగా ఎక్కడికి వెళ్తుందో కనిపించదు.",
    },
    "risky_domain": {
        "hi": "वेबसाइट का पता अजीब है (.xyz, .top जैसा)। असली बैंक ऐसे पते नहीं रखते।",
        "en": "The website address ends in something like .xyz or .top. Real banks do not use these.",
        "ta": "இணையதள முகவரி .xyz, .top போன்றது. உண்மையான வங்கிகள் இவற்றைப் பயன்படுத்துவதில்லை.",
        "te": "వెబ్‌సైట్ చిరునామా .xyz, .top లాంటిది. నిజమైన బ్యాంకులు ఇవి వాడవు.",
    },
    "phone_number": {
        "hi": "यह आपसे किसी मोबाइल नंबर पर फ़ोन करने को कहता है। बैंक का नंबर कार्ड के पीछे देखिए।",
        "en": "It asks you to call a mobile number. Use the number on the back of your card instead.",
        "ta": "ஒரு கைபேசி எண்ணை அழைக்கச் சொல்கிறது. உங்கள் கார்டின் பின்னால் உள்ள எண்ணையே அழையுங்கள்.",
        "te": "ఒక మొబైల్ నంబర్‌కు ఫోన్ చేయమంటోంది. మీ కార్డు వెనుక ఉన్న నంబర్‌కే ఫోన్ చేయండి.",
    },
    "urgency": {
        "hi": "यह जल्दी करने का दबाव डाल रहा है। ठग सोचने का समय नहीं देते।",
        "en": "It pushes you to hurry. Fraudsters do not want you to stop and think.",
        "ta": "அவசரப்படுத்துகிறது. மோசடிக்காரர்கள் யோசிக்க நேரம் தருவதில்லை.",
        "te": "తొందరపెడుతోంది. మోసగాళ్లు ఆలోచించే సమయం ఇవ్వరు.",
    },
    "threat": {
        "hi": "यह खाता बंद होने या बिजली कटने का डर दिखा रहा है।",
        "en": "It threatens that your account will be blocked or a service cut off.",
        "ta": "உங்கள் கணக்கு முடக்கப்படும் அல்லது சேவை துண்டிக்கப்படும் என்று பயமுறுத்துகிறது.",
        "te": "మీ ఖాతా బ్లాక్ అవుతుందని లేదా సేవ ఆగిపోతుందని భయపెడుతోంది.",
    },
    "prize": {
        "hi": "यह इनाम या लॉटरी जीतने की बात करता है जिसमें आपने हिस्सा नहीं लिया।",
        "en": "It says you won a prize or lottery you never entered.",
        "ta": "நீங்கள் பங்கேற்காத பரிசு அல்லது லாட்டரியை வென்றதாகச் சொல்கிறது.",
        "te": "మీరు పాల్గొనని బహుమతి లేదా లాటరీ గెలిచారని చెబుతోంది.",
    },
    "pay_to_receive": {
        "hi": "पैसे पाने के लिए पहले फीस माँग रहा है। पैसा पाने के लिए कभी पैसा नहीं देना पड़ता।",
        "en": "It asks for a fee before you receive money. You never pay to receive money.",
        "ta": "பணம் பெற முதலில் கட்டணம் கேட்கிறது. பணம் பெற ஒருபோதும் பணம் கட்டத் தேவையில்லை.",
        "te": "డబ్బు పొందడానికి ముందు రుసుము అడుగుతోంది. డబ్బు పొందడానికి ఎప్పుడూ డబ్బు కట్టనక్కర్లేదు.",
    },
    "remote_app": {
        "hi": "यह फ़ोन पर कोई ऐप (जैसे AnyDesk) डालने को कहता है। इससे कोई और आपका फ़ोन चला सकता है।",
        "en": "It asks you to install an app like AnyDesk, which lets a stranger control your phone.",
        "ta": "AnyDesk போன்ற செயலியை நிறுவச் சொல்கிறது; அதன் மூலம் வேறொருவர் உங்கள் போனை இயக்க முடியும்.",
        "te": "AnyDesk లాంటి యాప్ వేయమంటోంది; దాంతో వేరొకరు మీ ఫోన్‌ను నడపగలరు.",
    },
    "job_offer": {
        "hi": "घर बैठे आसान कमाई का वादा कर रहा है। ऐसी नौकरियाँ अक्सर ठगी होती हैं।",
        "en": "It promises easy money from home. Offers like this are very often fraud.",
        "ta": "வீட்டிலிருந்தே எளிதான வருமானம் என்கிறது. இவை பெரும்பாலும் மோசடி.",
        "te": "ఇంటి నుండే సులభమైన సంపాదన అంటోంది. ఇలాంటివి చాలా సార్లు మోసమే.",
    },
    "lookalike_chars": {
        "hi": "इसमें कुछ अक्षर नकली हैं जो असली नाम जैसे दिखते हैं।",
        "en": "Some letters are look-alikes, made to imitate a real company's name.",
        "ta": "சில எழுத்துகள் உண்மையான நிறுவனப் பெயரைப் போலத் தோன்றும் போலி எழுத்துகள்.",
        "te": "కొన్ని అక్షరాలు నిజమైన కంపెనీ పేరులా కనిపించే నకిలీవి.",
    },
}

# Fallback only -- the fitted weights in ml/artifacts/scam/rules.json win.
DEFAULT_WEIGHTS = {
    "asks_for_secret": 2.5, "mentions_secret": 0.2, "has_disclaimer": -2.0, "has_link": 1.0,
    "short_link": 1.2, "risky_domain": 1.5, "official_link": -1.0, "phone_number": 0.6,
    "toll_free": -0.5, "urgency": 0.8, "threat": 1.2, "prize": 1.3, "pay_to_receive": 1.6,
    "remote_app": 2.2, "job_offer": 1.0, "money_amount": 0.1, "lookalike_chars": 1.5,
}
DEFAULT_BIAS = -2.0


@dataclass
class RuleResult:
    features: dict[str, float]
    risk: float                     # P(not safe) under the rule model, 0..1
    fired: list[str]                # features that contributed risk, strongest first

    def reasons(self, language: str) -> list[str]:
        lang = language if language in LANGS else "en"
        return [REASONS[f][lang] for f in self.fired if f in REASONS]


def score(text: str, weights: dict[str, float] | None = None, bias: float | None = None) -> RuleResult:
    """Binary risk from the rule features alone, plus which ones fired."""
    w = weights or DEFAULT_WEIGHTS
    b = DEFAULT_BIAS if bias is None else bias
    feats = extract(text)
    z = b + sum(w.get(k, 0.0) * v for k, v in feats.items())
    risk = 1.0 / (1.0 + math.exp(-z))
    fired = sorted(
        (k for k, v in feats.items() if v and k not in SILENT and w.get(k, 0.0) > 0),
        key=lambda k: -w.get(k, 0.0),
    )
    return RuleResult(features=feats, risk=risk, fired=fired)
