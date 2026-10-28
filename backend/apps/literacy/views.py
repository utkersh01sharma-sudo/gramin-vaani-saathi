"""Lessons, quiz grading, and progress.

Answers are graded on the server and never sent to the client with the
questions. That is not about cheating -- nobody cheats at a literacy quiz on
their own phone -- it is so that progress means the same thing however the
client is built, and the explanation for each answer comes from one place.
"""
from __future__ import annotations

from django.conf import settings
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .catalog import PASS_FRACTION, get_lesson, load_lessons, localise
from .models import LessonProgress


def _lang(request) -> str:
    lang = request.query_params.get("lang") or (request.data.get("language") if request.method == "POST" else None)
    if lang in settings.SUPPORTED_LANGUAGES:
        return lang
    profile = getattr(request.user, "profile", None)
    return getattr(profile, "language", None) or settings.DEFAULT_LANGUAGE


def _progress_map(user) -> dict[str, LessonProgress]:
    return {p.lesson_id: p for p in LessonProgress.objects.filter(user=user)}


def _progress_dict(p: LessonProgress | None) -> dict:
    if p is None:
        return {"attempts": 0, "best_score": 0, "total": 0, "completed": False}
    return {"attempts": p.attempts, "best_score": p.best_score, "total": p.total,
            "completed": p.completed}


@extend_schema(tags=["literacy"], parameters=[OpenApiParameter("lang", str)], responses=OpenApiTypes.OBJECT)
class LessonListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        lang = _lang(request)
        progress = _progress_map(request.user)
        lessons = [{**localise(l, lang), "progress": _progress_dict(progress.get(l["id"]))}
                   for l in load_lessons()]
        done = sum(1 for l in lessons if l["progress"]["completed"])
        return Response({"language": lang, "completed": done, "total": len(lessons),
                         "results": lessons})


class QuizSerializer(serializers.Serializer):
    answers = serializers.ListField(child=serializers.IntegerField(min_value=0), max_length=20)
    language = serializers.ChoiceField(choices=["hi", "en", "ta", "te"], required=False)


@extend_schema(tags=["literacy"], request=QuizSerializer, responses=OpenApiTypes.OBJECT)
class QuizView(APIView):
    """Grade a quiz. Returns per-question correctness and the explanation for each."""

    permission_classes = [IsAuthenticated]

    def post(self, request, lesson_id: str):
        lesson = get_lesson(lesson_id)
        if lesson is None:
            return Response({"detail": "unknown lesson"}, status=status.HTTP_404_NOT_FOUND)
        s = QuizSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        answers = s.validated_data["answers"]
        quiz = lesson.get("quiz", [])
        if len(answers) != len(quiz):
            return Response({"detail": f"expected {len(quiz)} answers"},
                            status=status.HTTP_400_BAD_REQUEST)
        lang = _lang(request)

        results = []
        for q, given in zip(quiz, answers):
            results.append({
                "correct": given == q["answer"],
                "answer": q["answer"],
                "explain": q["explain"][lang],
            })
        score = sum(r["correct"] for r in results)
        passed = score >= PASS_FRACTION * len(quiz)

        progress, _ = LessonProgress.objects.get_or_create(user=request.user, lesson_id=lesson_id)
        progress.attempts += 1
        progress.total = len(quiz)
        progress.best_score = max(progress.best_score, score)
        progress.completed = progress.completed or passed
        progress.save()

        return Response({"lesson_id": lesson_id, "score": score, "total": len(quiz),
                         "passed": passed, "results": results,
                         "progress": _progress_dict(progress)})
