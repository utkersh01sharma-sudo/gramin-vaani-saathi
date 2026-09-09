"""Voice endpoints.

``/api/voice/text/`` takes an already-transcribed utterance. It exists on its own
rather than only as an internal step of the audio pipeline for three reasons:

* the PWA can use the browser's own SpeechRecognition where it is available and
  skip the audio round trip entirely,
* Tamil and Telugu can be demoed via typed or transliterated text on exactly the
  same NLU path if server-side ASR turns out to be weak on them,
* it makes the dialog layer testable without any audio fixtures.

``/api/voice/query/`` takes the audio itself. It transcribes, then funnels into
that same ``dialog.handle`` call, so there is exactly one copy of the rule that
says a payment needs confirming.
"""
import json
import uuid
from pathlib import Path

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings

from . import dialog
from .tasks import process_audio


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


# ------------------------------------------------------------------ audio
# MediaRecorder gives webm/opus on Chrome and mp4/aac on Safari; a plain file
# picker can hand us wav or m4a. PyAV decodes all of them, so the allow-list is
# about refusing obvious nonsense early rather than about codec support.
AUDIO_SUFFIXES = {".webm", ".ogg", ".oga", ".opus", ".wav", ".m4a", ".mp4", ".mp3", ".flac"}


class VoiceQuerySerializer(serializers.Serializer):
    audio = serializers.FileField()
    language = serializers.ChoiceField(
        choices=settings.SUPPORTED_LANGUAGES, required=False, allow_null=True
    )
    # Multipart cannot carry a JSON object, so the client sends the pending
    # action back as a JSON string in a form field.
    pending = serializers.CharField(required=False, allow_blank=True)

    def validate_audio(self, upload):
        if upload.size > settings.VOICE_MAX_UPLOAD_BYTES:
            raise serializers.ValidationError(
                f"Recording is larger than {settings.VOICE_MAX_UPLOAD_BYTES // 1024}KB. "
                "Speak one sentence at a time."
            )
        if Path(upload.name or "").suffix.lower() not in AUDIO_SUFFIXES:
            raise serializers.ValidationError("Unsupported audio format.")
        return upload

    def validate_pending(self, value):
        if not value:
            return None
        try:
            parsed = json.loads(value)
        except ValueError:
            raise serializers.ValidationError("pending must be JSON.")
        if not isinstance(parsed, dict):
            raise serializers.ValidationError("pending must be a JSON object.")
        return parsed


@extend_schema(tags=["voice"])
class VoiceQueryView(APIView):
    """Spoken utterance in, spoken reply out.

    The response shape depends on how the deployment is wired, and the client
    handles both because both are real:

    * with a broker (``CELERY_TASK_ALWAYS_EAGER=false``) this returns **202** and
      a ``task_id``; the client polls ``/api/voice/result/<id>/``. That is the
      configuration that scales, because the web worker is free again in
      milliseconds while a dedicated worker holds the GPU.
    * without one -- a laptop demo, an exam hall with no Redis -- the task runs
      inline and this returns **200** with the finished result. Same code path,
      same task function, no separate synchronous implementation to drift.

    Either way ``status`` says which happened, so the PWA never has to guess.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = VoiceQuerySerializer

    def post(self, request):
        serializer = VoiceQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        upload = data["audio"]
        suffix = Path(upload.name or "").suffix.lower() or ".webm"
        upload_dir = Path(settings.MEDIA_ROOT) / "uploads" / "voice"
        upload_dir.mkdir(parents=True, exist_ok=True)
        # The name is a UUID, never the client-supplied one: an uploaded filename
        # is attacker-controlled text and has no business steering a filesystem
        # path. The task deletes the file as soon as it has the transcript.
        path = upload_dir / f"{uuid.uuid4().hex}{suffix}"
        with open(path, "wb") as fh:
            for chunk in upload.chunks():
                fh.write(chunk)

        language = data.get("language") or dialog._language_for(request.user, None)
        async_result = process_audio.delay(
            str(path), request.user.pk, language, data.get("pending")
        )

        if settings.CELERY_TASK_ALWAYS_EAGER:
            payload = async_result.get()
            payload["status"] = "done"
            payload["task_id"] = async_result.id
            return Response(payload)

        return Response(
            {
                "status": "queued",
                "task_id": async_result.id,
                "poll_url": f"/api/voice/result/{async_result.id}/",
                "language": language,
            },
            status=status.HTTP_202_ACCEPTED,
        )


@extend_schema(tags=["voice"])
class VoiceResultView(APIView):
    """Poll a queued transcription.

    Kept dumb on purpose: it reports state and nothing else. The PWA polls this
    every 400 ms while showing a listening indicator, and a poll that costs a
    Redis lookup can be answered by any replica.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, task_id: str):
        from celery.result import AsyncResult

        from config.celery import app as celery_app

        result = AsyncResult(task_id, app=celery_app)

        if result.successful():
            payload = dict(result.result or {})
            payload["status"] = "done"
            payload["task_id"] = task_id
            return Response(payload)

        if result.failed():
            # The exception itself is logged server-side; the user gets a
            # sentence they can act on, in their own language.
            language = dialog._language_for(request.user, None)
            return Response(
                {
                    "status": "failed",
                    "task_id": task_id,
                    "reply_text": dialog.say("unclear", language),
                    "language": language,
                },
                status=status.HTTP_200_OK,
            )

        return Response({"status": "pending", "task_id": task_id}, status=status.HTTP_202_ACCEPTED)
