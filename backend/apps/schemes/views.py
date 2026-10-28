"""Scheme endpoints: the catalogue with a verdict per scheme, search, and a
what-if check.

Every response is already in the requested language and already explained.
The client never assembles an eligibility sentence itself; it reads out what
it is given. That keeps the four-language wording in one place -- the fixture --
and means the voice path and the screen say the same thing.
"""
from __future__ import annotations

from django.conf import settings
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ai.registry import get_embedder
from apps.accounts.models import UserProfile

from . import retrieval
from .catalog import get_scheme, load_schemes
from .engine import ELIGIBLE, MAYBE, check, check_all

LANG_PARAM = OpenApiParameter("lang", str, description="hi | en | ta | te")

# Fact fields the client is allowed to override in a what-if check. Anything
# else in the request body is ignored rather than passed into the rule engine.
FACT_FIELDS = (
    "age", "gender", "state", "occupation", "annual_income",
    "land_holding_acres", "has_bank_account", "is_bpl", "household_size",
)


def _lang(request) -> str:
    lang = request.query_params.get("lang")
    if not lang and request.method == "POST":
        lang = request.data.get("lang")
    if lang in settings.SUPPORTED_LANGUAGES:
        return lang
    profile = getattr(request.user, "profile", None)
    return getattr(profile, "language", None) or settings.DEFAULT_LANGUAGE


def _facts(user) -> dict:
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile.eligibility_facts()


def _summary(results: list[dict]) -> dict:
    return {
        "eligible": sum(r["verdict"] == ELIGIBLE for r in results),
        "maybe": sum(r["verdict"] == MAYBE for r in results),
        "total": len(results),
        # The facts that would turn the most MAYBEs into an answer, most useful
        # first. The client asks for these one at a time.
        "ask_next": _ask_next(results),
    }


def _ask_next(results: list[dict]) -> list[str]:
    counts: dict[str, int] = {}
    for r in results:
        if r["verdict"] == MAYBE:
            for f in r["missing_fields"]:
                counts[f] = counts.get(f, 0) + 1
    return sorted(counts, key=lambda f: -counts[f])


@extend_schema(tags=["schemes"], parameters=[LANG_PARAM])
class SchemeListView(APIView):
    """Every scheme, with this user's verdict and the reasons for it."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        lang = _lang(request)
        results = check_all(list(load_schemes()), _facts(request.user), lang)
        return Response({"language": lang, "summary": _summary(results), "results": results})


@extend_schema(
    tags=["schemes"],
    parameters=[LANG_PARAM, OpenApiParameter("q", str, description="What the user said")],
)
class SchemeSearchView(APIView):
    """Natural-language search, in any of the four languages."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        if not query:
            return Response({"detail": "q is required"}, status=status.HTTP_400_BAD_REQUEST)
        lang = _lang(request)
        k = min(int(request.query_params.get("k", 3)), 10)
        ranked, backend = retrieval.search(query, get_embedder(), k=k)
        facts = _facts(request.user)
        results = [{**check(s, facts, lang), "score": round(score, 4)} for s, score in ranked]
        return Response({"query": query, "language": lang, "backend": backend, "results": results})


@extend_schema(tags=["schemes"], parameters=[LANG_PARAM])
class SchemeCheckView(APIView):
    """Check one scheme, or all, against the profile plus optional overrides.

    Overrides answer "what if I were 60?" without writing to the profile, which
    is what the eligibility questions on the client use before saving.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        lang = _lang(request)
        facts = _facts(request.user)
        overrides = request.data.get("facts") or {}
        facts.update({k: v for k, v in overrides.items() if k in FACT_FIELDS})

        scheme_id = request.data.get("scheme_id")
        if scheme_id:
            scheme = get_scheme(scheme_id)
            if scheme is None:
                return Response({"detail": "unknown scheme"}, status=status.HTTP_404_NOT_FOUND)
            return Response({"language": lang, "result": check(scheme, facts, lang)})

        results = check_all(list(load_schemes()), facts, lang)
        return Response({"language": lang, "summary": _summary(results), "results": results})
