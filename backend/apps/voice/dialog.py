# -*- coding: utf-8 -*-
"""Turns an utterance into an action and a spoken reply.

This is the only place that decides *what happens*. The NLU adapter says what the
user meant; this module decides whether that meaning is allowed to touch the
ledger, and what sentence gets read back.

Two rules drive the design:

1. **Nothing that moves money executes on the first utterance.** Intents in
   ``CONFIRM_REQUIRED`` return ``needs_confirmation`` plus a ``pending`` object
   describing exactly what would happen. Only a second, affirmative utterance
   (or an explicit tap) carries it out.
2. **Pending state lives on the client, not in a session.** The server hands the
   pending action back out and expects to receive it again. That keeps every web
   worker stateless, so scaling out is adding replicas rather than adding sticky
   sessions.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation

from django.conf import settings

from ai.local.intent import fill_slots
from ai.registry import get_nlu
from apps.banking.models import SandboxAccount, Transaction, execute_transfer

# Intents that move money or change state. Mirrors ml/data/taxonomy.py; duplicated
# rather than imported because ml/ is not on the Django path in production.
CONFIRM_REQUIRED = {"send_money"}

INTENT_ICONS = {
    "check_balance": "wallet",
    "send_money": "send",
    "transaction_history": "history",
    "find_scheme": "scheme",
    "check_eligibility": "check",
    "scan_qr": "qr",
    "identify_note": "note",
    "report_scam": "alert",
    "check_scam": "shield",
    "learn_topic": "learn",
    "set_language": "language",
    "help": "help",
    "repeat": "repeat",
    "unknown": "question",
}

# Which PWA screen the reply should navigate to. Spoken answers and the icon-first
# UI have to agree, or a non-literate user loses the thread.
INTENT_SCREENS = {
    "check_balance": "balance",
    "send_money": "send",
    "transaction_history": "history",
    "find_scheme": "schemes",
    "check_eligibility": "schemes",
    "scan_qr": "scan",
    "identify_note": "scan",
    "report_scam": "safety",
    "check_scam": "safety",
    "learn_topic": "learn",
    "help": "help",
}

# ------------------------------------------------------------------ yes / no
AFFIRMATIVE = {
    "हाँ", "हां", "जी", "जी हाँ", "ठीक", "ठीक है", "भेज दो", "कर दो", "सही है", "हा",
    "haan", "han", "ha", "ji", "theek", "thik hai", "ok", "okay", "yes", "yeah", "yep",
    "sure", "confirm", "go ahead", "do it", "send it", "correct",
    "ஆம்", "சரி", "சரிதான்", "ஓகே", "அனுப்பு",
    "అవును", "సరే", "ఓకే", "పంపు", "సరైనది",
}

NEGATIVE = {
    "नहीं", "ना", "नही", "रुको", "रद्द", "मत भेजो", "छोड़ो", "गलत",
    "nahi", "nahin", "na", "no", "nope", "cancel", "stop", "wait", "wrong", "don't",
    "இல்லை", "வேண்டாம்", "நிறுத்து", "தவறு",
    "కాదు", "వద్దు", "ఆపు", "తప్పు",
}


def _classify_yes_no(text: str) -> str | None:
    """Return 'yes', 'no', or None. Longest-match wins so 'नहीं भेजो' is a no."""
    haystack = f" {text.strip().lower()} "
    hit_yes = max((len(w) for w in AFFIRMATIVE if f" {w} " in haystack or haystack.strip() == w), default=0)
    hit_no = max((len(w) for w in NEGATIVE if f" {w} " in haystack or haystack.strip() == w), default=0)
    if hit_no >= hit_yes and hit_no > 0:
        return "no"
    if hit_yes > 0:
        return "yes"
    return None


# ------------------------------------------------------------------ phrasebook
# Kept as flat templates rather than Django i18n .po files: these strings are
# *spoken*, they are edited constantly during tuning, and four languages of
# gettext catalogues would slow that loop down for no benefit.
R: dict[str, dict[str, str]] = {
    "balance": {
        "hi": "आपके खाते में {amount} रुपये हैं।",
        "en": "You have {amount} rupees in your account.",
        "ta": "உங்கள் கணக்கில் {amount} ரூபாய் உள்ளது.",
        "te": "మీ ఖాతాలో {amount} రూపాయలు ఉన్నాయి.",
    },
    "no_account": {
        "hi": "आपका खाता अभी नहीं खुला है।",
        "en": "You do not have a sandbox account yet.",
        "ta": "உங்களுக்கு இன்னும் கணக்கு இல்லை.",
        "te": "మీకు ఇంకా ఖాతా లేదు.",
    },
    "ask_amount": {
        "hi": "कितने रुपये भेजने हैं?",
        "en": "How many rupees should I send?",
        "ta": "எத்தனை ரூபாய் அனுப்ப வேண்டும்?",
        "te": "ఎన్ని రూపాయలు పంపాలి?",
    },
    "ask_payee": {
        "hi": "किसे भेजना है? नाम बोलिए।",
        "en": "Who should I send it to? Say the name.",
        "ta": "யாருக்கு அனுப்ப வேண்டும்? பெயரைச் சொல்லுங்கள்.",
        "te": "ఎవరికి పంపాలి? పేరు చెప్పండి.",
    },
    "confirm_send": {
        "hi": "{payee} को {amount} रुपये भेजें? हाँ या ना कहिए।",
        "en": "Send {amount} rupees to {payee}? Say yes or no.",
        "ta": "{payee} க்கு {amount} ரூபாய் அனுப்பவா? ஆம் அல்லது இல்லை என்று சொல்லுங்கள்.",
        "te": "{payee} కి {amount} రూపాయలు పంపాలా? అవును లేదా కాదు అని చెప్పండి.",
    },
    "sent": {
        "hi": "हो गया। {payee} को {amount} रुपये भेज दिए। अब आपके पास {balance} रुपये हैं।",
        "en": "Done. Sent {amount} rupees to {payee}. Your balance is now {balance} rupees.",
        "ta": "முடிந்தது. {payee} க்கு {amount} ரூபாய் அனுப்பப்பட்டது. இப்போது {balance} ரூபாய் உள்ளது.",
        "te": "అయిపోయింది. {payee} కి {amount} రూపాయలు పంపాను. ఇప్పుడు మీ వద్ద {balance} రూపాయలు ఉన్నాయి.",
    },
    "already_sent": {
        "hi": "यह पैसा पहले ही भेजा जा चुका है। दोबारा नहीं भेजा गया।",
        "en": "This payment was already made. It was not sent twice.",
        "ta": "இந்தப் பணம் ஏற்கனவே அனுப்பப்பட்டது. மீண்டும் அனுப்பப்படவில்லை.",
        "te": "ఈ డబ్బు ఇప్పటికే పంపబడింది. మళ్ళీ పంపలేదు.",
    },
    "insufficient": {
        "hi": "आपके खाते में इतने पैसे नहीं हैं। आपके पास {balance} रुपये हैं।",
        "en": "You do not have enough money. Your balance is {balance} rupees.",
        "ta": "உங்கள் கணக்கில் போதிய பணம் இல்லை. {balance} ரூபாய் மட்டுமே உள்ளது.",
        "te": "మీ ఖాతాలో సరిపడా డబ్బు లేదు. మీ వద్ద {balance} రూపాయలు ఉన్నాయి.",
    },
    "unknown_payee": {
        "hi": "यह नाम आपकी सूची में नहीं मिला। पैसा नहीं भेजा गया।",
        "en": "That name is not in your contact list. Nothing was sent.",
        "ta": "அந்தப் பெயர் உங்கள் பட்டியலில் இல்லை. பணம் அனுப்பப்படவில்லை.",
        "te": "ఆ పేరు మీ జాబితాలో లేదు. డబ్బు పంపలేదు.",
    },
    "cancelled": {
        "hi": "ठीक है, रद्द कर दिया। कोई पैसा नहीं गया।",
        "en": "Cancelled. No money was sent.",
        "ta": "ரத்து செய்யப்பட்டது. பணம் எதுவும் அனுப்பப்படவில்லை.",
        "te": "రద్దు చేశాను. డబ్బు ఏమీ పంపలేదు.",
    },
    "history_empty": {
        "hi": "अभी तक कोई लेनदेन नहीं हुआ है।",
        "en": "There are no transactions yet.",
        "ta": "இதுவரை பரிவர்த்தனை எதுவும் இல்லை.",
        "te": "ఇప్పటివరకు లావాదేవీలు ఏవీ లేవు.",
    },
    "history": {
        "hi": "पिछले लेनदेन: {items}।",
        "en": "Recent transactions: {items}.",
        "ta": "சமீபத்திய பரிவர்த்தனைகள்: {items}.",
        "te": "ఇటీవలి లావాదేవీలు: {items}.",
    },
    "sent_to": {"hi": "{name} को {amount} रुपये", "en": "{amount} rupees to {name}",
                "ta": "{name} க்கு {amount} ரூபாய்", "te": "{name} కి {amount} రూపాయలు"},
    "got_from": {"hi": "{name} से {amount} रुपये", "en": "{amount} rupees from {name}",
                 "ta": "{name} இடமிருந்து {amount} ரூபாய்", "te": "{name} నుండి {amount} రూపాయలు"},
    "schemes": {
        "hi": "सरकारी योजनाएँ खोल रहा हूँ। आप किस चीज़ के लिए मदद चाहते हैं?",
        "en": "Opening government schemes. What do you need help with?",
        "ta": "அரசுத் திட்டங்களைத் திறக்கிறேன். எதற்கு உதவி வேண்டும்?",
        "te": "ప్రభుత్వ పథకాలు తెరుస్తున్నాను. దేని కోసం సహాయం కావాలి?",
    },
    "learn": {
        "hi": "सीखने के पाठ खोल रहा हूँ।",
        "en": "Opening the learning lessons.",
        "ta": "பாடங்களைத் திறக்கிறேன்.",
        "te": "పాఠాలు తెరుస్తున్నాను.",
    },
    "scan": {
        "hi": "कैमरा खोलिए और कोड या नोट दिखाइए।",
        "en": "Open the camera and show the code or the note.",
        "ta": "கேமராவைத் திறந்து குறியீட்டையோ நோட்டையோ காட்டுங்கள்.",
        "te": "కెమెరా తెరిచి కోడ్ లేదా నోటు చూపించండి.",
    },
    "safety": {
        "hi": "सुरक्षा जाँच खोल रहा हूँ। संदेश पढ़कर सुनाइए या चिपकाइए।",
        "en": "Opening the safety check. Read out or paste the message.",
        "ta": "பாதுகாப்புச் சோதனையைத் திறக்கிறேன். செய்தியைப் படியுங்கள்.",
        "te": "భద్రతా తనిఖీ తెరుస్తున్నాను. సందేశం చదవండి.",
    },
    "language_set": {
        "hi": "अब मैं हिंदी में बात करूँगा।",
        "en": "I will speak in English now.",
        "ta": "இனி தமிழில் பேசுவேன்.",
        "te": "ఇక నుండి తెలుగులో మాట్లాడతాను.",
    },
    "help": {
        "hi": "आप कह सकते हैं: बैलेंस बताओ, पैसे भेजो, योजना बताओ, या कोड स्कैन करो।",
        "en": "You can say: check my balance, send money, find a scheme, or scan a code.",
        "ta": "நீங்கள் சொல்லலாம்: இருப்பு சொல், பணம் அனுப்பு, திட்டம் சொல், அல்லது கோடு ஸ்கேன் செய்.",
        "te": "మీరు చెప్పవచ్చు: బ్యాలెన్స్ చెప్పు, డబ్బు పంపు, పథకం చెప్పు, లేదా కోడ్ స్కాన్ చేయి.",
    },
    "unclear": {
        "hi": "मैंने ठीक से नहीं सुना। नीचे दिए चित्रों में से चुनिए, या फिर से बोलिए।",
        "en": "I did not catch that. Pick one of the pictures below, or say it again.",
        "ta": "எனக்குச் சரியாகக் கேட்கவில்லை. கீழே உள்ள படங்களில் ஒன்றைத் தேர்ந்தெடுங்கள்.",
        "te": "నాకు సరిగ్గా వినిపించలేదు. కింది బొమ్మల్లో ఒకటి ఎంచుకోండి.",
    },
    "scheme_found": {
        "hi": "आपके लिए ये योजनाएँ हैं: {items}।",
        "en": "These schemes may help you: {items}.",
        "ta": "உங்களுக்கான திட்டங்கள்: {items}.",
        "te": "మీ కోసం ఈ పథకాలు ఉన్నాయి: {items}.",
    },
    "scheme_none": {
        "hi": "इससे जुड़ी कोई योजना नहीं मिली। योजनाओं की पूरी सूची खोल रहा हूँ।",
        "en": "I did not find a matching scheme. Opening the full list of schemes.",
        "ta": "பொருந்தும் திட்டம் கிடைக்கவில்லை. முழுப் பட்டியலைத் திறக்கிறேன்.",
        "te": "సరిపోయే పథకం దొరకలేదు. పూర్తి జాబితా తెరుస్తున్నాను.",
    },
    "verdict_eligible": {"hi": "{name} — आप योग्य लगते हैं", "en": "{name}, which you appear to qualify for",
                         "ta": "{name} — நீங்கள் தகுதியானவர் போலத் தெரிகிறது", "te": "{name} — మీకు అర్హత ఉన్నట్లుంది"},
    "verdict_maybe": {"hi": "{name} — कुछ जानकारी और चाहिए", "en": "{name}, where I need a little more information",
                      "ta": "{name} — இன்னும் சில விவரம் தேவை", "te": "{name} — ఇంకొంచెం సమాచారం కావాలి"},
    "verdict_not": {"hi": "{name} — शायद आपके लिए नहीं", "en": "{name}, which may not apply to you",
                    "ta": "{name} — உங்களுக்குப் பொருந்தாமல் இருக்கலாம்", "te": "{name} — మీకు వర్తించకపోవచ్చు"},
    "scam_result": {"hi": "{headline}। {reason} {advice}", "en": "{headline}. {reason} {advice}",
                    "ta": "{headline}. {reason} {advice}", "te": "{headline}. {reason} {advice}"},
    "report_scam": {
        "hi": "घबराइए मत। अगर पैसा गया है तो अभी 1930 पर फ़ोन कीजिए। शिकायत का फ़ॉर्म खोल रहा हूँ।",
        "en": "Do not panic. If money was taken, call 1930 right now. Opening the report form.",
        "ta": "பதற வேண்டாம். பணம் போயிருந்தால் இப்போதே 1930-க்கு அழையுங்கள். புகார் படிவத்தைத் திறக்கிறேன்.",
        "te": "భయపడకండి. డబ్బు పోయి ఉంటే ఇప్పుడే 1930కి ఫోన్ చేయండి. ఫిర్యాదు ఫారం తెరుస్తున్నాను.",
    },
    # The title carries its own stop: "What is UPI?" must not become "UPI?.".
    "lesson_found": {"hi": "पाठ: {title} {first}", "en": "Lesson: {title} {first}",
                     "ta": "பாடம்: {title} {first}", "te": "పాఠం: {title} {first}"},
}


def say(key: str, language: str, **kwargs) -> str:
    template = R.get(key, {}).get(language) or R.get(key, {}).get("en", "")
    return template.format(**kwargs) if kwargs else template


# ------------------------------------------------------------------ result
@dataclass
class DialogResult:
    transcript: str
    language: str
    intent: str
    confidence: float
    slots: dict = field(default_factory=dict)
    reply_text: str = ""
    icon: str = "question"
    screen: str | None = None
    action_taken: str | None = None
    needs_confirmation: bool = False
    pending: dict | None = None
    nlu_backend: str = ""
    low_confidence: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _money(value) -> str:
    """Speak whole rupees as whole rupees -- '500', never '500.00'."""
    d = Decimal(str(value))
    return str(int(d)) if d == d.to_integral_value() else f"{d:.2f}"


# Unicode blocks per language, to tell whether a stored local name is in the
# script of the sentence it is about to be spoken in.
_SCRIPT_RANGES = {"hi": ("ऀ", "ॿ"), "ta": ("஀", "௿"), "te": ("ఀ", "౿")}


def _display_name(payee: dict, lang: str) -> str:
    """The payee's name in the reply's own script.

    A contact's ``name_local`` is in its *owner's* language, so a Hindi
    speaker's contact is stored in Devanagari. Read back inside an English or
    Tamil sentence that is wrong twice over: unreadable on screen, and
    mispronounced by the speech engine. Use it only when the script matches.
    """
    local = payee.get("name_local") or ""
    lo_hi = _SCRIPT_RANGES.get(lang)
    if local and lo_hi and any(lo_hi[0] <= ch <= lo_hi[1] for ch in local):
        return local
    return payee.get("name") or local or payee.get("vpa", "")


def _contacts_for(user) -> list[dict]:
    return list(user.contacts.values("name", "name_local", "vpa"))


def _language_for(user, requested: str | None) -> str:
    if requested in settings.SUPPORTED_LANGUAGES:
        return requested
    profile = getattr(user, "profile", None)
    return getattr(profile, "language", None) or settings.DEFAULT_LANGUAGE


# ------------------------------------------------------------------ handlers
def _handle_balance(user, lang: str, result: DialogResult) -> DialogResult:
    account = SandboxAccount.objects.filter(user=user).first()
    if account is None:
        result.reply_text = say("no_account", lang)
        return result
    result.reply_text = say("balance", lang, amount=_money(account.balance))
    result.action_taken = "read_balance"
    result.slots["balance"] = str(account.balance)
    return result


def _handle_history(user, lang: str, result: DialogResult) -> DialogResult:
    account = SandboxAccount.objects.filter(user=user).first()
    rows = list(account.transactions.all()[:3]) if account else []
    if not rows:
        result.reply_text = say("history_empty", lang)
        return result
    parts = []
    for txn in rows:
        key = "sent_to" if txn.direction == Transaction.Direction.DEBIT else "got_from"
        parts.append(
            say(key, lang, name=txn.counterparty_name or txn.counterparty_vpa,
                amount=_money(txn.amount))
        )
    result.reply_text = say("history", lang, items=", ".join(parts))
    result.action_taken = "read_history"
    return result


def _handle_send(user, lang: str, result: DialogResult) -> DialogResult:
    """Never executes. Collects slots, then asks for confirmation."""
    amount = result.slots.get("amount")
    payee = result.slots.get("payee")

    if not payee or not payee.get("match_confident"):
        result.reply_text = say("ask_payee", lang)
        result.action_taken = "ask_payee"
        result.slots["contacts"] = _contacts_for(user)
        return result
    if not amount:
        result.reply_text = say("ask_amount", lang)
        result.action_taken = "ask_amount"
        return result

    account = SandboxAccount.objects.filter(user=user).first()
    if account is None:
        result.reply_text = say("no_account", lang)
        return result
    if account.balance < Decimal(str(amount)):
        result.reply_text = say("insufficient", lang, balance=_money(account.balance))
        result.action_taken = "declined_insufficient_funds"
        return result

    # The idempotency key is minted here and handed to the client. Whether the
    # confirmation arrives now or after an offline queue replay tomorrow, the
    # same key reaches execute_transfer, so the money moves exactly once.
    result.needs_confirmation = True
    result.action_taken = "awaiting_confirmation"
    result.pending = {
        "action": "send_money",
        "amount": _money(amount),
        "payee_vpa": payee["vpa"],
        # Speak the name in the reply's script -- hearing "Ramesh" back after
        # saying "रमेश" reads as the app having misheard, and "सीता" inside an
        # English sentence cannot be read or pronounced.
        "payee_name": _display_name(payee, lang),
        "idempotency_key": f"voice-{uuid.uuid4()}",
    }
    result.reply_text = say(
        "confirm_send", lang, payee=result.pending["payee_name"],
        amount=result.pending["amount"],
    )
    return result


def _handle_scheme(user, lang: str, result: DialogResult) -> DialogResult:
    """Search the catalogue with what was said, and read back up to two matches
    with this user's verdict. The screen shows the full ranked list."""
    from ai.registry import get_embedder
    from apps.accounts.models import UserProfile
    from apps.schemes import retrieval
    from apps.schemes.engine import ELIGIBLE, MAYBE, check

    ranked, backend = retrieval.search(result.transcript, get_embedder(), k=3)
    if not ranked:
        result.reply_text = say("scheme_none", lang)
        result.action_taken = "navigate:schemes"
        return result
    profile, _ = UserProfile.objects.get_or_create(user=user)
    facts = profile.eligibility_facts()
    checks = [check(s, facts, lang) for s, _ in ranked]
    key = {ELIGIBLE: "verdict_eligible", MAYBE: "verdict_maybe"}
    items = ", ".join(say(key.get(c["verdict"], "verdict_not"), lang, name=c["name"]) for c in checks[:2])
    result.reply_text = say("scheme_found", lang, items=items)
    result.action_taken = "scheme_search"
    result.slots["schemes"] = [c["scheme_id"] for c in checks]
    result.slots["search_backend"] = backend
    return result


# A request to check a message is usually spoken with the message in it ("is
# this real: your account will be blocked..."). Below this many words it is
# just the request, and the user is sent to the screen to paste the message.
SCAM_MIN_WORDS = 8


_QUESTION_START = (
    "what", "how", "why", "where", "when", "should", "can", "is ", "do ", "does", "will", "who",
    "क्या", "कैसे", "क्यों", "कहाँ", "कहां", "कब", "किसे",
    "என்ன", "எப்படி", "ஏன்", "எங்கே", "எப்போது",
    "ఏమి", "ఎలా", "ఎందుకు", "ఎక్కడ", "ఎప్పుడు",
)
_QUESTION_END = ("?", "क्या", "कलामा", "லாமா", "ா?", "ఆ?", "నా?")


def _looks_like_question(text: str) -> bool:
    t = text.strip().lower()
    # Start or end only: a long scam message with a "?" in its middle is still a
    # message to score, not a question to answer.
    return t.startswith(_QUESTION_START) or t.endswith(_QUESTION_END)


def _handle_check_scam(user, lang: str, result: DialogResult) -> DialogResult:
    """A question about fraud gets a reviewed answer; a message gets a verdict.

    "Should I tell my OTP to the bank?" and "Your account will be blocked, update
    KYC at bit.ly/x" both classify as check_scam, but they need different
    things. Short or question-shaped utterances go to the knowledge base first;
    long ones are treated as a message being read out and scored by ScamNet.
    """
    words = len(result.transcript.split())
    if words < SCAM_MIN_WORDS or _looks_like_question(result.transcript):
        from ai.registry import get_embedder
        from apps.fraud import knowledge

        answer = knowledge.ask(result.transcript, get_embedder(), lang)
        if answer["answered"]:
            result.reply_text = answer["best"]["answer"]
            result.action_taken = "fraud_answer"
            result.slots["ask"] = answer
            return result
        if words < SCAM_MIN_WORDS:
            result.reply_text = say("safety", lang)
            result.action_taken = "navigate:safety"
            return result
    from apps.fraud.views import check_text

    verdict = check_text(user, result.transcript, lang)
    reason = verdict["reasons"][0] if verdict["reasons"] else ""
    result.reply_text = say("scam_result", lang, headline=verdict["headline"],
                            reason=reason, advice=verdict["advice"]).replace("  ", " ")
    result.action_taken = f"scam_check:{verdict['label']}"
    result.slots["scam"] = verdict
    return result


def _handle_report_scam(user, lang: str, result: DialogResult) -> DialogResult:
    result.reply_text = say("report_scam", lang)
    result.action_taken = "navigate:safety"
    result.slots["open"] = "report"
    return result


def _handle_learn(user, lang: str, result: DialogResult) -> DialogResult:
    """Pick the lesson whose title or steps share the most words with what was said."""
    from apps.literacy.catalog import load_lessons

    words = {w for w in result.transcript.lower().split() if len(w) > 2}
    best, best_hits = None, 0
    for lesson in load_lessons():
        text = " ".join([*lesson["title"].values(), *(" ".join(v) for v in lesson["steps"].values())]).lower()
        hits = sum(1 for w in words if w in text)
        if hits > best_hits:
            best, best_hits = lesson, hits
    if best is None:
        result.reply_text = say("learn", lang)
        result.action_taken = "navigate:learn"
        return result
    title = best["title"][lang]
    if not title.endswith(("?", "।", ".")):
        title += "।" if lang == "hi" else "."
    result.reply_text = say("lesson_found", lang, title=title, first=best["steps"][lang][0])
    result.action_taken = "open_lesson"
    result.slots["lesson_id"] = best["id"]
    return result


def confirm_pending(user, pending: dict, language: str) -> DialogResult:
    """Carry out a previously confirmed action. The only path to the ledger."""
    lang = _language_for(user, language)
    result = DialogResult(
        transcript="", language=lang, intent="send_money", confidence=1.0,
        icon="send", screen="balance",
    )

    try:
        amount = Decimal(str(pending["amount"]))
    except (KeyError, InvalidOperation):
        result.reply_text = say("unclear", lang)
        return result

    account = SandboxAccount.objects.filter(user=user).first()
    if account is None:
        result.reply_text = say("no_account", lang)
        return result

    txn, created = execute_transfer(
        account=account,
        to_vpa=pending["payee_vpa"],
        amount=amount,
        idempotency_key=pending["idempotency_key"],
        note=pending.get("note", ""),
        by_voice=True,
    )
    account.refresh_from_db()

    if txn.status == Transaction.Status.FAILED:
        if txn.failure_reason == "insufficient_funds":
            result.reply_text = say("insufficient", lang, balance=_money(account.balance))
        else:
            result.reply_text = say("unknown_payee", lang)
        result.action_taken = f"transfer_failed:{txn.failure_reason}"
    elif not created:
        # Replay of a key we have already settled. Say so out loud -- a user who
        # taps twice on a bad connection deserves to hear that it did not double.
        result.reply_text = say("already_sent", lang)
        result.action_taken = "transfer_replayed"
    else:
        result.reply_text = say(
            "sent", lang, payee=pending.get("payee_name", pending["payee_vpa"]),
            amount=_money(amount), balance=_money(account.balance),
        )
        result.action_taken = "transfer_executed"

    result.slots = {"transaction_id": str(txn.id), "status": txn.status}
    return result


# ------------------------------------------------------------------ entrypoint
def handle(user, text: str, language: str | None = None, pending: dict | None = None) -> DialogResult:
    """One utterance in, one spoken reply out.

    ``pending`` is the object this function returned on the previous turn. Its
    presence means the user is answering a yes/no question, so the utterance is
    read as an answer before it is read as a new command.
    """
    lang = _language_for(user, language)

    # --- answering a confirmation question
    if pending:
        answer = _classify_yes_no(text)
        if answer == "yes":
            return confirm_pending(user, pending, lang)
        if answer == "no":
            result = DialogResult(
                transcript=text, language=lang, intent="send_money", confidence=1.0,
                icon="send", action_taken="cancelled",
            )
            result.reply_text = say("cancelled", lang)
            return result
        # Neither yes nor no: re-ask rather than guessing at a payment.
        result = DialogResult(
            transcript=text, language=lang, intent="send_money", confidence=0.5,
            icon="send", needs_confirmation=True, pending=pending,
            action_taken="awaiting_confirmation",
        )
        result.reply_text = say(
            "confirm_send", lang, payee=pending.get("payee_name", ""),
            amount=pending.get("amount", ""),
        )
        return result

    nlu = get_nlu()
    prediction = nlu.predict(text, lang)
    slots = fill_slots(text, prediction.intent, _contacts_for(user))

    result = DialogResult(
        transcript=text,
        language=lang,
        intent=prediction.intent,
        confidence=prediction.confidence,
        slots=slots,
        icon=INTENT_ICONS.get(prediction.intent, "question"),
        screen=INTENT_SCREENS.get(prediction.intent),
        nlu_backend=getattr(nlu, "active_backend", getattr(nlu, "name", "")),
    )

    # Below threshold we stop guessing and hand the user the icon grid. Silently
    # acting on a 0.3-confidence "send money" is the worst outcome available.
    if prediction.confidence < settings.INTENT_MIN_CONFIDENCE or prediction.intent == "unknown":
        result.low_confidence = True
        result.intent = "unknown"
        result.icon = "question"
        result.screen = None
        result.reply_text = say("unclear", lang)
        return result

    handlers = {
        "check_balance": _handle_balance,
        "transaction_history": _handle_history,
        "send_money": _handle_send,
        "find_scheme": _handle_scheme,
        "check_eligibility": _handle_scheme,
        "check_scam": _handle_check_scam,
        "report_scam": _handle_report_scam,
        "learn_topic": _handle_learn,
    }
    if result.intent in handlers:
        return handlers[result.intent](user, lang, result)

    simple = {
        "scan_qr": "scan",
        "identify_note": "scan",
        "help": "help",
        "repeat": "help",
    }
    if result.intent in simple:
        result.reply_text = say(simple[result.intent], lang)
        result.action_taken = f"navigate:{result.screen}"
        return result

    if result.intent == "set_language":
        target = slots.get("language") or lang
        result.language = target
        result.reply_text = say("language_set", target)
        result.action_taken = f"set_language:{target}"
        return result

    result.reply_text = say("unclear", lang)
    return result
