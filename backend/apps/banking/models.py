"""Simulated banking ledger.

SAFETY: nothing in this module touches a real bank, PSP, or payment network.
Balances are rows in our own database seeded with play money. This is a student
project; it must never be pointed at a real rail.
"""
import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone


class InsufficientFunds(Exception):
    """Raised when a transfer would overdraw the sandbox account."""


class SandboxAccount(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="account"
    )
    account_number = models.CharField(max_length=18, unique=True)
    ifsc = models.CharField(max_length=11, default="SNDB0000001")
    bank_name = models.CharField(max_length=64, default="Sandbox Gramin Bank")
    vpa = models.CharField(max_length=64, unique=True, help_text="e.g. sita@sandbox")
    balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    daily_limit = models.DecimalField(max_digits=10, decimal_places=2, default=10000)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.vpa}: ₹{self.balance}"

    def masked_account_number(self) -> str:
        return f"XXXX{self.account_number[-4:]}"

    def spent_today(self):
        from django.db.models import Sum

        today = timezone.localdate()
        total = self.transactions.filter(
            direction=Transaction.Direction.DEBIT,
            status=Transaction.Status.SUCCESS,
            created_at__date=today,
        ).aggregate(s=Sum("amount"))["s"]
        return total or 0


class Transaction(models.Model):
    """One ledger entry.

    ``idempotency_key`` is unique and supplied by the *client*. The PWA generates
    it before queueing an offline action, so replaying the same queued transfer
    after reconnect returns the original result instead of moving money twice.
    """

    class Direction(models.TextChoices):
        DEBIT = "debit", "Money out"
        CREDIT = "credit", "Money in"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        SandboxAccount, on_delete=models.CASCADE, related_name="transactions"
    )
    idempotency_key = models.CharField(max_length=64, unique=True, db_index=True)
    direction = models.CharField(max_length=6, choices=Direction.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    counterparty_vpa = models.CharField(max_length=64, blank=True)
    counterparty_name = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    failure_reason = models.CharField(max_length=128, blank=True)
    note = models.CharField(max_length=140, blank=True)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    initiated_by_voice = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        sign = "-" if self.direction == self.Direction.DEBIT else "+"
        return f"{sign}₹{self.amount} {self.counterparty_name or self.counterparty_vpa}"


@transaction.atomic
def execute_transfer(
    *,
    account: SandboxAccount,
    to_vpa: str,
    amount,
    idempotency_key: str,
    note: str = "",
    by_voice: bool = False,
) -> tuple[Transaction, bool]:
    """Move play money between two sandbox accounts.

    Returns ``(txn, created)``. When ``created`` is False the key was already
    seen and the original transaction is returned unchanged -- this is the
    replay-safety guarantee the offline queue depends on.
    """
    existing = Transaction.objects.filter(idempotency_key=idempotency_key).first()
    if existing is not None:
        return existing, False

    # Lock the payer row so two concurrent transfers cannot both read the old balance.
    payer = SandboxAccount.objects.select_for_update().get(pk=account.pk)
    payee = SandboxAccount.objects.select_for_update().filter(vpa=to_vpa).first()

    txn = Transaction(
        account=payer,
        idempotency_key=idempotency_key,
        direction=Transaction.Direction.DEBIT,
        amount=amount,
        counterparty_vpa=to_vpa,
        counterparty_name=payee.user.get_full_name() or payee.user.username if payee else "",
        note=note,
        initiated_by_voice=by_voice,
    )

    if payee is None:
        txn.status = Transaction.Status.FAILED
        txn.failure_reason = "unknown_payee"
        txn.save()
        return txn, True

    if payer.balance < amount:
        txn.status = Transaction.Status.FAILED
        txn.failure_reason = "insufficient_funds"
        txn.balance_after = payer.balance
        txn.save()
        return txn, True

    payer.balance -= amount
    payee.balance += amount
    payer.save(update_fields=["balance"])
    payee.save(update_fields=["balance"])

    txn.status = Transaction.Status.SUCCESS
    txn.balance_after = payer.balance
    txn.save()

    # Mirror entry so the payee also sees the money arrive.
    Transaction.objects.create(
        account=payee,
        idempotency_key=f"{idempotency_key}:credit",
        direction=Transaction.Direction.CREDIT,
        amount=amount,
        counterparty_vpa=payer.vpa,
        counterparty_name=payer.user.get_full_name() or payer.user.username,
        status=Transaction.Status.SUCCESS,
        balance_after=payee.balance,
        note=note,
    )
    return txn, True
