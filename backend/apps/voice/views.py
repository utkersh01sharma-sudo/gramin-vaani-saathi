"""Voice endpoints.

``/api/voice/text/`` takes an already-transcribed utterance. It exists on its own
rather than only as an internal step of the audio pipeline for three reasons:

* the PWA can use the browser's own SpeechRecognition where it is available and
  skip the audio round trip entirely,
* Tamil and Telugu can be demoed via typed or transliterated text on exactly the
  same NLU path if server-side ASR turns out to be weak on them,
* it makes the dialog layer testable without any audio fixtures.

Audio upload (``/api/voice/query/``) lands on Day 2 and will funnel into the same
``dialog.handle`` call after transcription.
"""
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings

from . import dialog


class VoiceTextSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=500, allow_blank=False, trim_whitespace=True)
    language = serializers.ChoiceField(
        choices=settings.SUPPORTED_LANGUAGES, required=False, allow_null=True
    )
    # Echoed back from the previous response when the user is answering a
    # confirmation question. Keeping it client-side leaves the API stateless.
    pending = serializers.JSONField(required=False, allow_null=True)


class ConfirmSerializer(serializers.Serializer):
    pending = serializers.JSONField()
    language = serializers.ChoiceField(
        choices=settings.SUPPORTED_LANGUAGES, required=False, allow_null=True
    )


@extend_schema(tags=["voice"])
class VoiceTextView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VoiceTextSerializer

    def post(self, request):
        serializer = VoiceTextSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = dialog.handle(
            user=request.user,
            text=data["text"],
            language=data.get("language"),
            pending=data.get("pending") or None,
        )
        return Response(result.to_dict())


@extend_schema(tags=["voice"])
class VoiceConfirmView(APIView):
    """Explicit tap-to-confirm, for users who would rather press the green tick
    than say the word. Same code path, same idempotency key."""

    permission_classes = [IsAuthenticated]
    serializer_class = ConfirmSerializer

    def post(self, request):
        serializer = ConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pending = serializer.validated_data["pending"] or {}

        required = {"action", "amount", "payee_vpa", "idempotency_key"}
        if not required.issubset(pending):
            return Response(
                {"detail": "Malformed pending action."}, status=status.HTTP_400_BAD_REQUEST
            )

        result = dialog.confirm_pending(
            request.user, pending, serializer.validated_data.get("language")
        )
        return Response(result.to_dict(), status=status.HTTP_201_CREATED)
