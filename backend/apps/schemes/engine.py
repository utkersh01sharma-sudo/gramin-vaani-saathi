"""Declarative eligibility: does this person qualify, and *why*.

A black-box "you are not eligible" is useless to the person it is addressed to.
They cannot tell whether the answer is wrong, whether they typed something
badly, or what would have to change for it to become yes. For someone who
cannot read the scheme's own guidelines, that answer is worse than no answer --
it closes the question without informing it.

So every rule here carries its own reason string in all four languages, and the
engine returns the reason for each rule it evaluated, pass or fail. The reply
the user hears is "you qualify because you farm and own less than two hectares",
or "you would qualify, but this one is only for women". Both are actionable.

Three verdicts, not two:

    ELIGIBLE      every rule passed
    NOT_ELIGIBLE  at least one rule failed on a fact we actually know
    MAYBE         no rule failed, but at least one could not be evaluated
                  because the profile does not have that fact yet

MAYBE is the important one. A profile that has never been filled in would
otherwise fail every income test and the user would be told they qualify for
nothing, which is both wrong and discouraging. Instead the engine says "we need
to know your yearly income" and the app can ask that one question.

The rules are data, loaded from fixtures/schemes.json, not code. That is what
lets a scheme be corrected -- and they change every budget -- without a deploy
of Python, and it is why the operators below are a small closed set rather than
anything resembling eval().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

ELIGIBLE = "eligible"
NOT_ELIGIBLE = "not_eligible"
MAYBE = "maybe"

LANGUAGES = ("hi", "en", "ta", "te")


# --------------------------------------------------------------------- operators
# Each returns True/False. They are never handed a None fact -- the engine
# short-circuits to MAYBE before calling one -- so no operator needs to guess
# what a missing value means.

def _op_eq(fact: Any, value: Any) -> bool:
    return fact == value


def _op_in(fact: Any, value: Any) -> bool:
    return fact in value


def _op_not_in(fact: Any, value: Any) -> bool:
    return fact not in value


def _op_lte(fact: Any, value: Any) -> bool:
    return float(fact) <= float(value)


def _op_gte(fact: Any, value: Any) -> bool:
    return float(fact) >= float(value)


def _op_between(fact: Any, value: Any) -> bool:
    low, high = value
    return float(low) <= float(fact) <= float(high)


def _op_is_true(fact: Any, value: Any) -> bool:
    return bool(fact) is True


def _op_is_false(fact: Any, value: Any) -> bool:
    return bool(fact) is False


OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
    "eq": _op_eq,
    "in": _op_in,
    "not_in": _op_not_in,
    "lte": _op_lte,
    "gte": _op_gte,
    "between": _op_between,
    "is_true": _op_is_true,
    "is_false": _op_is_false,
}

# Operators that do not read a `value` from the rule.
UNARY = {"is_true", "is_false"}


class RuleError(ValueError):
    """A scheme fixture is malformed. Raised at load time, never at request time."""


# ------------------------------------------------------------------------ rule
@dataclass(frozen=True)
class Rule:
    field: str
    op: str
    value: Any
    reason: dict[str, str]          # why this rule matters, per language
    unmet: dict[str, str]           # what to say when it fails, per language

    @classmethod
    def from_dict(cls, raw: dict, *, scheme_id: str) -> "Rule":
        missing = {"field", "op", "reason", "unmet"} - set(raw)
        if missing:
            raise RuleError(f"{scheme_id}: rule is missing {sorted(missing)}")
        if raw["op"] not in OPERATORS:
            raise RuleError(f"{scheme_id}: unknown operator {raw['op']!r}")
        if raw["op"] not in UNARY and "value" not in raw:
            raise RuleError(f"{scheme_id}: operator {raw['op']!r} needs a value")
        for label in ("reason", "unmet"):
            absent = [lang for lang in LANGUAGES if not raw[label].get(lang)]
            if absent:
                raise RuleError(f"{scheme_id}: {label} has no text for {absent}")
        return cls(
            field=raw["field"],
            op=raw["op"],
            value=raw.get("value"),
            reason=raw["reason"],
            unmet=raw["unmet"],
        )

    def evaluate(self, facts: dict) -> bool | None:
        """True / False, or None when the fact needed is not known yet."""
        fact = facts.get(self.field)
        if fact is None or fact == "":
            return None
        return OPERATORS[self.op](fact, self.value)


# ---------------------------------------------------------------------- scheme
@dataclass(frozen=True)
class Scheme:
    id: str
    name: dict[str, str]
    summary: dict[str, str]
    benefit: dict[str, str]
    category: str
    icon: str
    tone: str
    rules: tuple[Rule, ...] = field(default=())
    # Free-text keywords used by the retrieval fallback when no embedding model
    # is installed. Not eligibility -- purely for "what can I get for farming".
    keywords: tuple[str, ...] = field(default=())

    @classmethod
    def from_dict(cls, raw: dict) -> "Scheme":
        scheme_id = raw.get("id")
        if not scheme_id:
            raise RuleError("a scheme in the fixture has no id")
        for label in ("name", "summary", "benefit"):
            absent = [lang for lang in LANGUAGES if not raw.get(label, {}).get(lang)]
            if absent:
                raise RuleError(f"{scheme_id}: {label} has no text for {absent}")
        return cls(
            id=scheme_id,
            name=raw["name"],
            summary=raw["summary"],
            benefit=raw["benefit"],
            category=raw.get("category", "other"),
            icon=raw.get("icon", "scheme"),
            tone=raw.get("tone", "var(--tone-scheme)"),
            rules=tuple(Rule.from_dict(r, scheme_id=scheme_id) for r in raw.get("rules", [])),
            keywords=tuple(raw.get("keywords", [])),
        )


# ---------------------------------------------------------------------- verdict
def check(scheme: Scheme, facts: dict, language: str = "hi") -> dict:
    """Evaluate one scheme against one profile. Returns the full explanation."""
    language = language if language in LANGUAGES else "hi"

    met: list[str] = []
    unmet: list[str] = []
    unknown: list[str] = []
    missing_fields: list[str] = []

    for rule in scheme.rules:
        outcome = rule.evaluate(facts)
        if outcome is None:
            unknown.append(rule.reason[language])
            missing_fields.append(rule.field)
        elif outcome:
            met.append(rule.reason[language])
        else:
            unmet.append(rule.unmet[language])

    if unmet:
        verdict = NOT_ELIGIBLE
    elif unknown:
        verdict = MAYBE
    else:
        verdict = ELIGIBLE

    return {
        "scheme_id": scheme.id,
        "name": scheme.name[language],
        "summary": scheme.summary[language],
        "benefit": scheme.benefit[language],
        "category": scheme.category,
        "icon": scheme.icon,
        "tone": scheme.tone,
        "verdict": verdict,
        "reasons_met": met,
        "reasons_unmet": unmet,
        "reasons_unknown": unknown,
        # The app asks for these one at a time rather than showing a form.
        "missing_fields": sorted(set(missing_fields)),
    }


def check_all(schemes: list[Scheme], facts: dict, language: str = "hi") -> list[dict]:
    """Evaluate every scheme, best verdict first.

    Order is eligible, then maybe, then not eligible. Someone scrolling an audio
    list hears the things they can actually get before the things they cannot,
    which is the only ordering that respects their time.
    """
    rank = {ELIGIBLE: 0, MAYBE: 1, NOT_ELIGIBLE: 2}
    results = [check(scheme, facts, language) for scheme in schemes]
    results.sort(key=lambda r: (rank[r["verdict"]], r["scheme_id"]))
    return results
