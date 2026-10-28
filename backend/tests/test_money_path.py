"""The money path: idempotent transfers, offline replay, and confirmation.

These are the guarantees the README makes. If any of these fail, the app can
move play money twice -- and the whole design exists to make that impossible.
"""
from decimal import Decimal

from apps.banking.models import SandboxAccount, Transaction, execute_transfer
from apps.voice import dialog


def _balances():
    return {a.vpa: a.balance for a in SandboxAccount.objects.all()}


def test_same_idempotency_key_moves_money_once(sita):
    account = sita.account
    before = _balances()
    first, created_1 = execute_transfer(account=account, to_vpa="ramesh@sandbox",
                                        amount=Decimal("100"), idempotency_key="k-1")
    second, created_2 = execute_transfer(account=account, to_vpa="ramesh@sandbox",
                                         amount=Decimal("100"), idempotency_key="k-1")
    after = _balances()

    assert created_1 and not created_2
    assert first.pk == second.pk
    assert Transaction.objects.filter(idempotency_key="k-1").count() == 1
    assert after["sita@sandbox"] == before["sita@sandbox"] - 100
    assert after["ramesh@sandbox"] == before["ramesh@sandbox"] + 100


def test_insufficient_funds_fails_without_moving_money(sita):
    before = _balances()
    txn, _ = execute_transfer(account=sita.account, to_vpa="ramesh@sandbox",
                              amount=Decimal("99999999"), idempotency_key="k-big")
    assert txn.status == Transaction.Status.FAILED
    assert txn.failure_reason == "insufficient_funds"
    assert _balances() == before


def test_unknown_payee_fails_without_moving_money(sita):
    before = _balances()
    txn, _ = execute_transfer(account=sita.account, to_vpa="nobody@nowhere",
                              amount=Decimal("10"), idempotency_key="k-unknown")
    assert txn.failure_reason == "unknown_payee"
    assert _balances() == before


def test_offline_queue_replay_is_idempotent(client_for):
    """The same queued item replayed twice -- e.g. the response was lost on a
    flaky connection and the client retried -- settles exactly once."""
    client = client_for("sita")
    item = {"pending": {"action": "send_money", "amount": "25", "payee_vpa": "lakshmi@sandbox",
                        "payee_name": "Lakshmi", "idempotency_key": "queued-1"}, "language": "en"}
    before = _balances()

    first = client.post("/api/sync/replay/", {"items": [item]}, format="json").json()
    retry = client.post("/api/sync/replay/", {"items": [item, item]}, format="json").json()

    assert first["executed"] == 1
    assert retry["executed"] == 0 and retry["replayed"] == 2
    assert _balances()["sita@sandbox"] == before["sita@sandbox"] - 25


def test_send_money_never_executes_on_first_utterance(sita):
    """The dialog collects slots and asks; it does not touch the ledger."""
    result = dialog.DialogResult(
        transcript="ramesh ko 50 bhejo", language="hi", intent="send_money", confidence=0.9,
        slots={"amount": 50, "payee": {"vpa": "ramesh@sandbox", "name": "Ramesh",
                                       "name_local": "रमेश", "match_confident": True}},
    )
    before = Transaction.objects.count()
    out = dialog._handle_send(sita, "hi", result)

    assert out.needs_confirmation is True
    assert out.pending["idempotency_key"].startswith("voice-")
    assert Transaction.objects.count() == before


def test_confirmation_answers():
    assert dialog._classify_yes_no("हाँ भेज दो") == "yes"
    assert dialog._classify_yes_no("नहीं भेजो") == "no"      # longest match wins
    assert dialog._classify_yes_no("ok") == "yes"
    assert dialog._classify_yes_no("வேண்டாம்") == "no"
    assert dialog._classify_yes_no("tomorrow maybe") is None


def test_unclear_answer_reasks_instead_of_paying(sita):
    pending = {"action": "send_money", "amount": "20", "payee_vpa": "ramesh@sandbox",
               "payee_name": "Ramesh", "idempotency_key": "k-unclear"}
    before = Transaction.objects.count()
    out = dialog.handle(sita, "what time is it", "en", pending=pending)
    assert out.needs_confirmation and out.pending == pending
    assert Transaction.objects.count() == before
