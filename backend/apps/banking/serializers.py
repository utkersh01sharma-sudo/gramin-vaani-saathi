from decimal import Decimal

from rest_framework import serializers

from .models import SandboxAccount, Transaction


class AccountSerializer(serializers.ModelSerializer):
    masked_account_number = serializers.CharField(read_only=True)
    spent_today = serializers.SerializerMethodField()

    class Meta:
        model = SandboxAccount
        fields = [
            "vpa",
            "masked_account_number",
            "bank_name",
            "ifsc",
            "balance",
            "daily_limit",
            "spent_today",
        ]

    def get_spent_today(self, obj) -> str:
        return str(obj.spent_today())


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            "id",
            "direction",
            "amount",
            "counterparty_vpa",
            "counterparty_name",
            "status",
            "failure_reason",
            "note",
            "balance_after",
            "initiated_by_voice",
            "created_at",
        ]


class TransferSerializer(serializers.Serializer):
    to_vpa = serializers.CharField(max_length=64)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("1.00"))
    idempotency_key = serializers.CharField(max_length=64)
    note = serializers.CharField(max_length=140, required=False, allow_blank=True)
    by_voice = serializers.BooleanField(required=False, default=False)

    def validate_amount(self, value):
        # Sandbox ceiling. Keeps a mis-parsed voice amount ("do lakh") from
        # producing an absurd ledger entry during a demo.
        if value > 100000:
            raise serializers.ValidationError("Amount exceeds the sandbox limit.")
        return value
