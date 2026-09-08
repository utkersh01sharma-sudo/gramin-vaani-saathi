# -*- coding: utf-8 -*-
"""Expand the template bank into a balanced, noised intent-classification dataset.

Why generate rather than scrape: there is no public corpus of rural Indian
voice-banking commands in Hindi/Tamil/Telugu. Templates plus slot fillers plus
ASR-style corruption gets us a training set with honest coverage of the phrasings
we actually expect.

IMPORTANT: the *test* set used for the reported metrics is hand-written
(ml/data/intent_test_handwritten.jsonl), not generated. Evaluating generated data
against generated data would only measure how well the model memorised our
templates. Run this file, then train, then evaluate on the hand-written set.

Usage:
    python ml/data/generate_intent_data.py --n-per-intent 550
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

# Windows consoles default to cp1252 and cannot print Devanagari/Tamil/Telugu.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lexicon import (  # noqa: E402
    AMOUNTS_DIGIT,
    AMOUNTS_LATIN_WORD,
    AMOUNTS_WORD,
    LANGUAGE_NAMES,
    PERSONS,
    PERSONS_LATIN,
    SCHEMES,
    TOPICS,
)
from taxonomy import INTENTS  # noqa: E402
from templates import TEMPLATES  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent

# Disfluencies a real speaker produces and Whisper faithfully transcribes.
FILLERS = {
    "hi": ["अच्छा", "सुनो", "जी", "अरे", "हां तो", "भैया"],
    "en": ["um", "okay so", "listen", "hey", "please"],
    "ta": ["சரி", "கேளுங்க", "அண்ணா"],
    "te": ["సరే", "వినండి", "అన్నా"],
}

POLITE_SUFFIX = {
    "hi": ["", "", "", " जी", " प्लीज", " भैया"],
    "en": ["", "", "", " please", " thanks"],
    "ta": ["", "", "", " ப்ளீஸ்", " அண்ணா"],
    "te": ["", "", "", " ప్లీజ్", " అన్నా"],
}


def fillers_for(lang: str, latin: bool) -> dict:
    """Slot values appropriate to the language and script."""
    if latin:
        return {
            "person": PERSONS_LATIN,
            "amount": AMOUNTS_DIGIT + AMOUNTS_LATIN_WORD,
            "topic": TOPICS["en"],
            "scheme": SCHEMES["en"],
            "language": ["Hindi", "English", "Tamil", "Telugu"],
        }
    return {
        "person": PERSONS[lang],
        "amount": AMOUNTS_DIGIT + AMOUNTS_WORD[lang],
        "topic": TOPICS[lang],
        "scheme": SCHEMES[lang],
        "language": [n for names in LANGUAGE_NAMES.values() for n in names],
    }


def apply_asr_noise(text: str, rng: random.Random) -> str:
    """Simulate the ways ASR output differs from clean text."""
    words = text.split()
    roll = rng.random()

    if roll < 0.12 and len(words) > 3:
        # Dropped word -- common on the first syllable of an utterance.
        words.pop(rng.randrange(len(words)))
    elif roll < 0.20 and len(words) > 2:
        # Stutter / repeated word.
        i = rng.randrange(len(words))
        words.insert(i, words[i])
    elif roll < 0.26:
        # Word order wobble in the middle of the sentence.
        if len(words) > 3:
            i = rng.randrange(len(words) - 1)
            words[i], words[i + 1] = words[i + 1], words[i]

    return " ".join(words)


def build_examples(n_per_intent: int, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    rows: list[dict] = []

    for intent in INTENTS:
        variants = TEMPLATES[intent]
        # Group by language, then sample language-first. Sampling templates
        # uniformly would over-represent Hindi purely because it has the most
        # templates; we want roughly equal numbers per language.
        by_lang: dict[str, list[tuple[str, bool]]] = {}
        for key, templates in variants.items():
            latin = key.endswith("_latin")
            lang = key.replace("_latin", "")
            by_lang.setdefault(lang, []).extend((tpl, latin) for tpl in templates)
        langs = sorted(by_lang)
        pool_size = sum(len(v) for v in by_lang.values())

        seen: set[tuple[str, str]] = set()
        attempts = 0
        made = 0
        while made < n_per_intent and attempts < n_per_intent * 40:
            attempts += 1
            lang = rng.choice(langs)
            tpl, latin = rng.choice(by_lang[lang])
            values = fillers_for(lang, latin)

            slots: dict[str, str] = {}
            text = tpl
            for key, options in values.items():
                token = "{" + key + "}"
                if token in text:
                    choice = rng.choice(options)
                    slots[key] = choice
                    text = text.replace(token, choice)

            # Optional leading filler word.
            if rng.random() < 0.15:
                text = f"{rng.choice(FILLERS[lang])} {text}"
            # Optional polite suffix.
            text = text + rng.choice(POLITE_SUFFIX[lang])
            # Optional ASR corruption.
            if rng.random() < 0.30:
                text = apply_asr_noise(text, rng)
            # Casing noise: ASR is inconsistent about capitalisation.
            if latin or lang == "en":
                r = rng.random()
                if r < 0.25:
                    text = text.lower()
                elif r < 0.30:
                    text = text.upper()

            text = " ".join(text.split())
            key_pair = (text, lang)
            if key_pair in seen:
                continue
            seen.add(key_pair)

            rows.append(
                {
                    "text": text,
                    "intent": intent,
                    "language": lang,
                    "script": "latin" if latin else "native",
                    "slots": slots,
                }
            )
            made += 1

        if made < n_per_intent:
            print(
                f"  warn: {intent} produced only {made}/{n_per_intent} unique rows "
                f"({pool_size} templates available)"
            )

    rng.shuffle(rows)
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-per-intent", type=int, default=550)
    parser.add_argument("--val-fraction", type=float, default=0.12)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    print(f"Generating {args.n_per_intent} examples for each of {len(INTENTS)} intents...")
    rows = build_examples(args.n_per_intent, seed=args.seed)

    split = int(len(rows) * (1 - args.val_fraction))
    train, val = rows[:split], rows[split:]

    write_jsonl(OUT_DIR / "intent_train.jsonl", train)
    write_jsonl(OUT_DIR / "intent_val.jsonl", val)

    print(f"\n  train: {len(train):>6} rows -> ml/data/intent_train.jsonl")
    print(f"  val:   {len(val):>6} rows -> ml/data/intent_val.jsonl")

    by_lang: dict[str, int] = {}
    by_script: dict[str, int] = {}
    for row in rows:
        by_lang[row["language"]] = by_lang.get(row["language"], 0) + 1
        by_script[row["script"]] = by_script.get(row["script"], 0) + 1
    print(f"\n  by language: {by_lang}")
    print(f"  by script:   {by_script}")
    print("\n  Sample rows:")
    for row in rows[:6]:
        print(f"    [{row['intent']:<20}] ({row['language']}) {row['text']}")


if __name__ == "__main__":
    main()
