"""Scam check and scam report endpoints."""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ai.registry import get_embedder, get_scam

from . import knowledge

from .models import ScamCheck, ScamReport

MAX_MESSAGE_CHARS = 2000

# What to do next, by what happened. Speed matters for money_lost: the national
# helpline can ask banks to hold funds, and that only works within hours.
NEXT_STEPS = {
    "money_lost": {
        "hi": ["अभी 1930 पर फ़ोन कीजिए। जितनी जल्दी, पैसा रुकने की उतनी उम्मीद।",
               "अपने बैंक को फ़ोन करके खाता और कार्ड बंद करवाइए।",
               "cybercrime.gov.in पर शिकायत लिखवाइए।"],
        "en": ["Call 1930 right now. The sooner you call, the better the chance the money is held.",
               "Call your bank and ask them to block your account and card.",
               "File a complaint at cybercrime.gov.in."],
        "ta": ["இப்போதே 1930-க்கு அழையுங்கள். விரைவாக அழைத்தால் பணம் நிறுத்தப்பட வாய்ப்பு அதிகம்.",
               "உங்கள் வங்கியை அழைத்து கணக்கையும் கார்டையும் முடக்கச் சொல்லுங்கள்.",
               "cybercrime.gov.in-ல் புகார் பதிவு செய்யுங்கள்."],
        "te": ["ఇప్పుడే 1930కి ఫోన్ చేయండి. ఎంత త్వరగా చేస్తే డబ్బు ఆగే అవకాశం అంత ఎక్కువ.",
               "మీ బ్యాంకుకు ఫోన్ చేసి ఖాతా, కార్డు బ్లాక్ చేయమనండి.",
               "cybercrime.gov.in లో ఫిర్యాదు చేయండి."],
    },
    "shared_details": {
        "hi": ["अपने बैंक को तुरंत फ़ोन करके कार्ड और UPI बंद करवाइए।", "अपना UPI PIN और पासवर्ड बदलिए।",
               "अगर पैसा कटे तो 1930 पर फ़ोन कीजिए।"],
        "en": ["Call your bank now and block your card and UPI.", "Change your UPI PIN and passwords.",
               "If any money is taken, call 1930."],
        "ta": ["உடனே வங்கியை அழைத்து கார்டு, UPI-ஐ முடக்குங்கள்.", "UPI PIN, கடவுச்சொல்லை மாற்றுங்கள்.",
               "பணம் போனால் 1930-க்கு அழையுங்கள்."],
        "te": ["వెంటనే బ్యాంకుకు ఫోన్ చేసి కార్డు, UPI బ్లాక్ చేయించండి.", "UPI PIN, పాస్‌వర్డ్ మార్చండి.",
               "డబ్బు పోతే 1930కి ఫోన్ చేయండి."],
    },
    "message_only": {
        "hi": ["उस संदेश का जवाब मत दीजिए और लिंक मत खोलिए।", "नंबर को ब्लॉक कीजिए।",
               "चाहें तो sancharsaathi.gov.in पर 'चक्षु' में शिकायत कीजिए।"],
        "en": ["Do not reply to the message or open its link.", "Block the number.",
               "You can report it under 'Chakshu' on sancharsaathi.gov.in."],
        "ta": ["அந்தச் செய்திக்குப் பதில் அனுப்பாதீர்கள், இணைப்பைத் திறக்காதீர்கள்.", "எண்ணைத் தடுங்கள்.",
               "sancharsaathi.gov.in-ல் 'சக்ஷு' பகுதியில் புகார் செய்யலாம்."],
        "te": ["ఆ సందేశానికి జవాబు ఇవ్వకండి, లింక్ తెరవకండి.", "నంబర్‌ను బ్లాక్ చేయండి.",
               "sancharsaathi.gov.in లో 'చక్షు'లో ఫిర్యాదు చేయవచ్చు."],
    },
}


def _lang(request) -> str:
    lang = request.data.get("language") or request.query_params.get("lang")
    if lang in settings.SUPPORTED_LANGUAGES:
        return lang
    profile = getattr(request.user, "profile", None)
    return getattr(profile, "language", None) or settings.DEFAULT_LANGUAGE


def check_text(user, text: str, lang: str) -> dict:
    """Score, log and explain one message. Shared with the voice dialog."""
    detector = get_scam()
    verdict = detector.classify(text, lang)
    backend = getattr(detector, "active_backend", getattr(detector, "name", ""))
    copy = detector.explain(verdict, lang) if hasattr(detector, "explain") else {}
    ScamCheck.objects.create(
        user=user, text=text, language=lang, label=verdict.label, score=verdict.score,
        model_score=verdict.model_score, rule_score=verdict.rule_score,
        reasons=verdict.reasons, backend=backend,
    )
    return {
        "label": verdict.label,
        "score": verdict.score,
        "headline": copy.get("headline", verdict.label),
        "reasons": verdict.reasons,
        "advice": copy.get("advice", ""),
        "model_score": verdict.model_score,
        "rule_score": verdict.rule_score,
        "backend": backend,
        "language": lang,
    }


class CheckSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=MAX_MESSAGE_CHARS)
    language = serializers.ChoiceField(choices=["hi", "en", "ta", "te"], required=False)


@extend_schema(tags=["fraud"], request=CheckSerializer, responses=OpenApiTypes.OBJECT)
class ScamCheckView(APIView):
    """Is this message a scam? Returns a verdict, the reasons, and what to do."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = CheckSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(check_text(request.user, s.validated_data["text"].strip(), _lang(request)))


@extend_schema(tags=["fraud"], responses=OpenApiTypes.OBJECT)
class ScamHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rows = request.user.scam_checks.all()[:20]
        return Response({"results": [
            {"text": r.text, "label": r.label, "score": r.score, "reasons": r.reasons,
             "created_at": r.created_at} for r in rows
        ]})


class ReportSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=ScamReport.Kind.choices)
    description = serializers.CharField(max_length=MAX_MESSAGE_CHARS, required=False, allow_blank=True)
    message_text = serializers.CharField(max_length=MAX_MESSAGE_CHARS, required=False, allow_blank=True)
    amount_lost = serializers.DecimalField(max_digits=12, decimal_places=2, required=False,
                                           allow_null=True, min_value=Decimal("0"))
    language = serializers.ChoiceField(choices=["hi", "en", "ta", "te"], required=False)


@extend_schema(tags=["fraud"], request=ReportSerializer, responses=OpenApiTypes.OBJECT)
class ScamReportView(APIView):
    """Record what happened and return the steps to take, in order.

    The app does not -- cannot -- file a police complaint. The response says
    where to file one, and the first step for lost money is always the 1930
    helpline because only a fast call can get funds held.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = ReportSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = {k: v for k, v in s.validated_data.items() if k != "language"}
        report = ScamReport.objects.create(user=request.user, **data)
        lang = _lang(request)
        return Response({
            "id": report.id,
            "kind": report.kind,
            "helpline": "1930",
            "portal": "https://cybercrime.gov.in",
            "next_steps": NEXT_STEPS[report.kind][lang],
        }, status=status.HTTP_201_CREATED)


class AskSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=500)
    language = serializers.ChoiceField(choices=["hi", "en", "ta", "te"], required=False)


@extend_schema(tags=["fraud"], request=AskSerializer, responses=OpenApiTypes.OBJECT)
class AskView(APIView):
    """Search the fraud-safety knowledge base: a question in, a reviewed answer out.

    Questions are not stored. People describe what happened to them in their own
    words -- names, amounts, numbers -- and there is no reason to keep that.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = AskSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(knowledge.ask(s.validated_data["text"].strip(), get_embedder(), _lang(request)))


@extend_schema(tags=["fraud"], responses=OpenApiTypes.OBJECT)
class QuestionListView(APIView):
    """Suggested questions to show before the user has typed anything."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        lang = _lang(request)
        return Response({"language": lang, "results": knowledge.featured(lang)})
