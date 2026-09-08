"""Single source of truth for the intent label set.

Imported by the dataset generator, the trainer, and the Django NLU adapter so the
label order can never drift between training and inference.
"""

INTENTS = [
    "check_balance",
    "send_money",
    "transaction_history",
    "find_scheme",
    "check_eligibility",
    "scan_qr",
    "identify_note",
    "report_scam",
    "check_scam",
    "learn_topic",
    "set_language",
    "help",
    "repeat",
    "unknown",
]

LABEL2ID = {label: i for i, label in enumerate(INTENTS)}
ID2LABEL = {i: label for label, i in LABEL2ID.items()}

# Intents that move money or change state need an explicit spoken confirmation
# before execution. Never act on the first utterance for these.
CONFIRM_REQUIRED = {"send_money"}

# Icon shown alongside the spoken reply, for non-literate navigation.
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

LANGUAGES = ["hi", "en", "ta", "te"]
