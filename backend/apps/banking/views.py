from decimal import Decimal

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SandboxAccount, execute_transfer
from .serializers import AccountSerializer, TransactionSerializer, TransferSerializer


def get_account(user) -> SandboxAccount | None:
    return SandboxAccount.objects.filter(user=user).first()


@extend_schema(tags=["banking"])
class AccountView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AccountSerializer

    def get(self, request):
        account = get_account(request.user)
        if account is None:
            return Response({"detail": "No sandbox account."}, status=status.HTTP_404_NOT_FOUND)
        return Response(AccountSerializer(account).data)


@extend_schema(tags=["banking"])
class TransferView(APIView):
    """Move play money between sandbox accounts.

    A failed transfer still returns 201 with ``status: "failed"``: a declined
    payment is a recorded ledger event the user needs read back to them, not an
    HTTP-level error the client has to special-case.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = TransferSerializer

    def post(self, request):
        serializer = TransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        account = get_account(request.user)
        if account is None:
            return Response({"detail": "No sandbox account."}, status=status.HTTP_404_NOT_FOUND)

        txn, created = execute_transfer(
            account=account,
            to_vpa=data["to_vpa"],
            amount=Decimal(data["amount"]),
            idempotency_key=data["idempotency_key"],
            note=data.get("note", ""),
            by_voice=data.get("by_voice", False),
        )
        return Response(
            {"transaction": TransactionSerializer(txn).data, "replayed": not created},
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["banking"])
class TransactionListView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TransactionSerializer

    def get(self, request):
        account = get_account(request.user)
        if account is None:
            return Response({"results": []})
        try:
            limit = min(int(request.query_params.get("limit", 20)), 100)
        except ValueError:
            limit = 20
        qs = account.transactions.all()[:limit]
        return Response({"results": TransactionSerializer(qs, many=True).data})
