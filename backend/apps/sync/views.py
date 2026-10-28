"""Replay the offline queue in one request.

The client queues confirmed actions while offline, each carrying the
idempotency key minted when the user said yes. On reconnect it sends the whole
queue here. Every item goes through the same confirm_pending() path a live tap
uses, so the ledger's idempotency check is the only thing deciding whether
money moves: an action the server already settled before the connection
dropped comes back as "replayed", not as a second payment.

Items are processed in the order the user made them and independently -- one
failing (insufficient funds after an earlier item) does not stop the rest, and
the response reports each outcome so the client can tell the user exactly what
happened to each thing they asked for.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.voice.dialog import confirm_pending

MAX_ITEMS = 50


class PendingSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["send_money"])
    amount = serializers.CharField(max_length=16)
    payee_vpa = serializers.CharField(max_length=64)
    payee_name = serializers.CharField(max_length=64, required=False, allow_blank=True)
    idempotency_key = serializers.CharField(max_length=64)


class ItemSerializer(serializers.Serializer):
    pending = PendingSerializer()
    language = serializers.ChoiceField(choices=["hi", "en", "ta", "te"], required=False)
    queued_at = serializers.IntegerField(required=False)


class ReplaySerializer(serializers.Serializer):
    items = ItemSerializer(many=True, max_length=MAX_ITEMS)


@extend_schema(tags=["sync"], request=ReplaySerializer)
class ReplayView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = ReplaySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        results = []
        for item in sorted(s.validated_data["items"], key=lambda i: i.get("queued_at", 0)):
            pending = dict(item["pending"])
            outcome = confirm_pending(request.user, pending, item.get("language"))
            action = outcome.action_taken or ""
            status = ("executed" if action == "transfer_executed" else
                      "replayed" if action == "transfer_replayed" else "failed")
            results.append({
                "idempotency_key": pending["idempotency_key"],
                "status": status,
                "detail": action,
                "reply_text": outcome.reply_text,
                "transaction_id": outcome.slots.get("transaction_id"),
            })
        return Response({
            "results": results,
            "executed": sum(r["status"] == "executed" for r in results),
            "replayed": sum(r["status"] == "replayed" for r in results),
            "failed": sum(r["status"] == "failed" for r in results),
        })
