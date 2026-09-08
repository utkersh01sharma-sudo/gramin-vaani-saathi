# -*- coding: utf-8 -*-
"""Rule-based slot extraction for amounts and payee names.

Deliberately rules rather than a learned tagger. A token-classification head
needs far more labelled data than one week allows, and a mis-parsed *amount* is
the single most expensive error this app can make -- rules are auditable and fail
predictably, which matters more here than squeezing out a few points of F1.

Every extracted amount is spoken back to the user for confirmation before any
money moves (see apps/voice/dialog.py), so a parse error is caught by the user,
not by the ledger.
"""
from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------- number words
# Multiplicative units, applied to the count that precedes them.
UNITS = {
    # Hindi / Devanagari
    "सौ": 100, "हजार": 1000, "हज़ार": 1000, "लाख": 100000,
    # Hindi transliterated
    "sau": 100, "hazaar": 1000, "hazar": 1000, "hajar": 1000, "lakh": 100000,
    # English
    "hundred": 100, "thousand": 1000, "k": 1000,
    # Tamil
    "நூறு": 100, "ஆயிரம்": 1000, "இலட்சம்": 100000, "லட்சம்": 100000,
    # Telugu
    "వంద": 100, "వందలు": 100, "వెయ్యి": 1000, "వేలు": 1000, "లక్ష": 100000,
}

# Standalone counts and irregular forms.
DIGITS = {
    # Hindi / Devanagari
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "सात": 7,
    "आठ": 8, "नौ": 9, "दस": 10, "बीस": 20, "पचास": 50, "सौ": 100,
    # Hindi transliterated
    "ek": 1, "do": 2, "teen": 3, "char": 4, "paanch": 5, "panch": 5, "chah": 6,
    "saat": 7, "aath": 8, "nau": 9, "das": 10, "bees": 20, "pachas": 50,
    # English
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "twenty": 20, "fifty": 50,
    # Tamil
    "ஒன்று": 1, "இரண்டு": 2, "மூன்று": 3, "நான்கு": 4, "ஐந்து": 5, "பத்து": 10,
    "இருபது": 20, "ஐம்பது": 50, "இருநூறு": 200, "ஐநூறு": 500, "நானூறு": 400,
    "முந்நூறு": 300, "இரண்டாயிரம்": 2000,
    # Telugu
    "ఒకటి": 1, "రెండు": 2, "మూడు": 3, "నాలుగు": 4, "ఐదు": 5, "పది": 10,
    "ఇరవై": 20, "యాభై": 50, "మూడు వందల": 300, "రెండు వేలు": 2000,
}

# Currency mentions, used only to locate an amount -- never as the amount itself.
CURRENCY_WORDS = {
    "रुपये", "रुपए", "रूपाय", "रुपया", "rupaye", "rupees", "rupee", "rs", "inr",
    "ரூபாய்", "ரூபாயை", "రూపాయలు", "రూపాయల", "paise", "पैसे", "money", "पैसा",
}

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_TAMIL_DIGITS = str.maketrans("௦௧௨௩௪௫௬௭௮௯", "0123456789")
_TELUGU_DIGITS = str.maketrans("౦౧౨౩౪౫౬౭౮౯", "0123456789")


def normalize(text: str) -> str:
    """NFC-normalise and map Indic digit glyphs to ASCII digits."""
    text = unicodedata.normalize("NFC", text)
    return text.translate(_DEVANAGARI_DIGITS).translate(_TAMIL_DIGITS).translate(_TELUGU_DIGITS)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[\wऀ-ॿ஀-௿ఀ-౿]+", text.lower())


def _eval_run(run: list[str]) -> float:
    """Evaluate one contiguous number phrase using Indian composition.

    "do sau pachas" -> 2*100 + 50 = 250; "sau" alone -> 100; "2 hazaar" -> 2000.
    """
    total = 0.0
    current = 0.0
    for token in run:
        if token in UNITS:
            # A unit with no preceding count means one of it ("sau" = 100).
            current = (current or 1.0) * UNITS[token]
            total += current
            current = 0.0
        elif re.fullmatch(r"\d+(?:\.\d{1,2})?", token):
            current += float(token)
        elif token in DIGITS:
            current += float(DIGITS[token])
    return total + current


def extract_amount(text: str) -> float | None:
    """Return the rupee amount mentioned, or None.

    Handles bare digits ("500"), word units ("paanch sau", "पांच सौ", "ஐநூறு"),
    and mixed forms ("2 hazaar"). Returns None rather than guessing when nothing
    parses -- the dialog layer then asks the user for the amount explicitly.

    Number tokens are grouped into *contiguous* runs rather than summed across the
    whole sentence. Several Indian number words double as ordinary verbs -- Hindi
    "do" is both "two" and the imperative "give" -- so "paanch sau rupaye de do"
    must read as 500, not 502. Requiring adjacency is what separates them.
    """
    text = normalize(text)
    raw_tokens = re.findall(r"\d+(?:\.\d{1,2})?|[\wऀ-ॿ஀-௿ఀ-౿]+", text.lower())

    def is_number_token(token: str) -> bool:
        return (
            token in UNITS
            or token in DIGITS
            or bool(re.fullmatch(r"\d+(?:\.\d{1,2})?", token))
        )

    # Collect contiguous number runs with the token index each one starts at.
    runs: list[tuple[int, int, list[str]]] = []
    current: list[str] = []
    start = 0
    for i, token in enumerate(raw_tokens):
        if is_number_token(token):
            if not current:
                start = i
            current.append(token)
        elif current:
            runs.append((start, i, current))
            current = []
    if current:
        runs.append((start, len(raw_tokens), current))

    if not runs:
        return None

    def touches_currency(begin: int, end: int) -> bool:
        """True when a currency word sits immediately before or after the run."""
        before = raw_tokens[begin - 1] if begin > 0 else ""
        after = raw_tokens[end] if end < len(raw_tokens) else ""
        return before in CURRENCY_WORDS or after in CURRENCY_WORDS

    # A run next to "rupaye"/"rupees" is far more likely to be the amount than a
    # stray number word elsewhere in the sentence. Ties break on earliest mention.
    scored = [
        (touches_currency(begin, end), -begin, _eval_run(run))
        for begin, end, run in runs
    ]
    scored.sort(reverse=True)
    best = scored[0][2]
    return best if best > 0 else None


def extract_payee(text: str, contacts: list[dict]) -> dict | None:
    """Match a spoken name against the user's contact list.

    ``contacts`` is a list of ``{"name", "name_local", "vpa"}``. Matching is
    restricted to the user's own contacts on purpose: resolving an arbitrary
    spoken name to an arbitrary VPA is exactly how a voice assistant would
    misdirect a payment.
    """
    if not contacts:
        return None

    normalized = normalize(text).lower()
    tokens = set(_tokens(normalized))

    best: tuple[int, dict] | None = None
    for contact in contacts:
        for candidate in (contact.get("name", ""), contact.get("name_local", "")):
            if not candidate:
                continue
            cand = normalize(candidate).lower()
            score = 0
            if cand in normalized:
                # Longer literal matches beat shorter ones.
                score = 100 + len(cand)
            elif cand in tokens:
                score = 90
            else:
                # Tolerate ASR dropping or altering a trailing syllable.
                for token in tokens:
                    if len(token) >= 4 and len(cand) >= 4 and (
                        token.startswith(cand[:4]) or cand.startswith(token[:4])
                    ):
                        score = max(score, 50 + min(len(token), len(cand)))
            if score and (best is None or score > best[0]):
                best = (score, contact)

    if best is None:
        return None
    score, contact = best
    return {**contact, "match_score": score, "match_confident": score >= 90}
