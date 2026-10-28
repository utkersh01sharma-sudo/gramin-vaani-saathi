"""The scheme catalogue: fixtures/schemes.json, validated once per process.

Every scheme passes through ``Scheme.from_dict`` at load, so a malformed rule --
an unknown operator, a missing translation -- fails the first request after a
deploy (and the test suite before it), never a user's eligibility check halfway
through a conversation.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .engine import Scheme

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "schemes.json"


@lru_cache(maxsize=1)
def load_schemes() -> tuple[Scheme, ...]:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    schemes = tuple(Scheme.from_dict(item) for item in raw["schemes"])
    ids = [s.id for s in schemes]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f"duplicate scheme ids in fixture: {sorted(duplicates)}")
    return schemes


def get_scheme(scheme_id: str) -> Scheme | None:
    return next((s for s in load_schemes() if s.id == scheme_id), None)
