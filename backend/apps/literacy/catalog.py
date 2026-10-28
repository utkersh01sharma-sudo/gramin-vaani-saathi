"""Lessons from fixtures/lessons.json, validated once per process."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "lessons.json"
LANGUAGES = ("hi", "en", "ta", "te")

# Two thirds right counts as learned: with two options per question, three out
# of three can be luck an eighth of the time, and two out of three cannot be
# reached by always picking the same button on every lesson.
PASS_FRACTION = 2 / 3


class LessonError(ValueError):
    pass


def _check(lesson: dict) -> dict:
    lid = lesson.get("id") or "?"
    for key in ("title", "steps"):
        missing = [l for l in LANGUAGES if not lesson.get(key, {}).get(l)]
        if missing:
            raise LessonError(f"{lid}: {key} missing {missing}")
    for i, q in enumerate(lesson.get("quiz", [])):
        for key in ("q", "options", "explain"):
            missing = [l for l in LANGUAGES if not q.get(key, {}).get(l)]
            if missing:
                raise LessonError(f"{lid} q{i}: {key} missing {missing}")
        sizes = {len(q["options"][l]) for l in LANGUAGES}
        if len(sizes) != 1:
            raise LessonError(f"{lid} q{i}: option count differs between languages")
        if not 0 <= q["answer"] < sizes.pop():
            raise LessonError(f"{lid} q{i}: answer index out of range")
    return lesson


@lru_cache(maxsize=1)
def load_lessons() -> tuple[dict, ...]:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return tuple(_check(lesson) for lesson in raw["lessons"])


def get_lesson(lesson_id: str) -> dict | None:
    return next((l for l in load_lessons() if l["id"] == lesson_id), None)


def localise(lesson: dict, lang: str) -> dict:
    """The lesson in one language, without the answers -- those stay server-side."""
    return {
        "id": lesson["id"],
        "icon": lesson.get("icon", "learn"),
        "tone": lesson.get("tone", "var(--tone-learn)"),
        "minutes": lesson.get("minutes", 1),
        "title": lesson["title"][lang],
        "steps": lesson["steps"][lang],
        "quiz": [{"q": q["q"][lang], "options": q["options"][lang]} for q in lesson.get("quiz", [])],
    }
