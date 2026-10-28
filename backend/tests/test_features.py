# -*- coding: utf-8 -*-
"""Schemes, scam checks, lessons and QR: catalogue integrity and API contracts."""
from pathlib import Path

import pytest

from ai.local import scam_rules
from ai.local.vision import parse_upi
from apps.literacy.catalog import load_lessons
from apps.schemes.catalog import load_schemes
from apps.schemes.engine import ELIGIBLE, MAYBE, NOT_ELIGIBLE, Rule, RuleError, Scheme, check

SAMPLES = Path(__file__).resolve().parents[2] / "docs" / "samples"


# ------------------------------------------------------------------ schemes
def test_scheme_fixture_loads_and_validates():
    schemes = load_schemes()
    assert len(schemes) == 20
    assert all(s.rules for s in schemes)


def test_unknown_operator_is_rejected_at_load_time():
    with pytest.raises(RuleError):
        Rule.from_dict({"field": "age", "op": "eval", "value": "1",
                        "reason": {l: "x" for l in "hi en ta te".split()},
                        "unmet": {l: "x" for l in "hi en ta te".split()}}, scheme_id="t")


def _toy_scheme():
    text = {l: "x" for l in ("hi", "en", "ta", "te")}
    return Scheme.from_dict({
        "id": "toy", "name": text, "summary": text, "benefit": text,
        "rules": [
            {"field": "age", "op": "gte", "value": 60, "reason": text, "unmet": {**text, "en": "too young"}},
            {"field": "is_bpl", "op": "is_true", "reason": text, "unmet": text},
        ],
    })


def test_three_verdicts_with_reasons():
    scheme = _toy_scheme()
    assert check(scheme, {"age": 70, "is_bpl": True}, "en")["verdict"] == ELIGIBLE
    unmet = check(scheme, {"age": 30, "is_bpl": True}, "en")
    assert unmet["verdict"] == NOT_ELIGIBLE and unmet["reasons_unmet"] == ["too young"]
    # An empty profile must not be told it qualifies for nothing.
    maybe = check(scheme, {"is_bpl": True}, "en")
    assert maybe["verdict"] == MAYBE and maybe["missing_fields"] == ["age"]


def test_scheme_api_and_what_if(client_for):
    client = client_for("sita")
    listing = client.get("/api/schemes/?lang=en").json()
    assert listing["summary"]["total"] == 20
    first = listing["results"][0]
    assert {"verdict", "reasons_met", "reasons_unmet", "name"} <= first.keys()

    old = client.post("/api/schemes/check/", {"scheme_id": "nsap-old-age", "facts": {"age": 75},
                                              "lang": "en"}, format="json").json()["result"]
    young = client.post("/api/schemes/check/", {"scheme_id": "nsap-old-age", "facts": {"age": 25},
                                                "lang": "en"}, format="json").json()["result"]
    # Changing only the age override removes exactly the age rule's failure.
    assert young["verdict"] == NOT_ELIGIBLE
    assert len(old["reasons_unmet"]) == len(young["reasons_unmet"]) - 1


def test_scheme_search_keyword_fallback(client_for, monkeypatch):
    """With no embedding model the search still answers, from keywords, and says so."""
    from apps.schemes import views

    monkeypatch.setattr(views, "get_embedder", lambda: None)
    data = client_for("sita").get("/api/schemes/search/?q=kisan farmer&lang=en").json()
    assert data["backend"] == "keyword"
    assert data["results"][0]["scheme_id"] in {"pm-kisan", "kcc", "pmfby"}


# ------------------------------------------------------------------ scam
def test_genuine_otp_message_is_not_flagged_by_rules():
    """The hard negative: a real bank OTP mentions the OTP and says not to share it."""
    r = scam_rules.score("482913 is your OTP. Do not share it with anyone. -SBI")
    assert r.features["has_disclaimer"] == 1 and r.features["asks_for_secret"] == 0
    assert r.risk < 0.2


def test_phishing_features_fire():
    # "immediately", not a bare "now": genuine alerts say "your balance is now..." too.
    f = scam_rules.extract("Share the OTP immediately or your account will be blocked: bit.ly/x1")
    assert f["asks_for_secret"] and f["short_link"] and f["threat"] and f["urgency"]


def test_lookalike_characters():
    assert scam_rules.extract("pаytm cashback")["lookalike_chars"] == 1   # Cyrillic а


def test_scam_endpoint_contract(client_for, rules_only_scam):
    client = client_for("sita")
    body = client.post("/api/fraud/check/", {"text": "You won the KBC lottery! Pay Rs 500 processing "
                                                     "fee to claim. Call 9876543210", "language": "en"},
                       format="json").json()
    assert body["label"] in {"suspicious", "scam"}
    assert body["reasons"] and body["advice"] and body["backend"].startswith("rules")
    history = client.get("/api/fraud/history/").json()["results"]
    assert history and history[0]["label"] == body["label"]


def test_scam_report_points_to_1930(client_for):
    body = client_for("sita").post("/api/fraud/report/", {"kind": "money_lost", "language": "en"},
                                   format="json").json()
    assert body["helpline"] == "1930" and "1930" in body["next_steps"][0]


# ------------------------------------------------------------------ literacy
def test_lessons_validate_and_hide_answers(client_for):
    assert len(load_lessons()) == 8
    lessons = client_for("sita").get("/api/literacy/lessons/?lang=hi").json()["results"]
    assert all("answer" not in q for l in lessons for q in l["quiz"])


def test_quiz_grading_keeps_best_score(client_for):
    client = client_for("sita")
    good = client.post("/api/literacy/lessons/upi/quiz/", {"answers": [1, 0, 0]}, format="json").json()
    bad = client.post("/api/literacy/lessons/upi/quiz/", {"answers": [0, 1, 1]}, format="json").json()
    assert good["passed"] and good["score"] == 3
    assert not bad["passed"]
    assert bad["progress"]["best_score"] == 3 and bad["progress"]["completed"]


# ------------------------------------------------------------------ vision
def test_parse_upi():
    p = parse_upi("upi://pay?pa=ramkirana@sandbox&pn=Ram%20Kirana&am=250&url=http://x.top")
    assert p["is_upi"] and p["pa"] == "ramkirana@sandbox" and p["am"] == 250.0 and p["url"]
    assert not parse_upi("https://example.com")["is_upi"]


@pytest.mark.parametrize("sample, level, must_warn", [
    ("qr_shop_genuine.png", "ok", set()),
    ("qr_sticker_tampered.png", "danger", {"possible_sticker", "unknown_payee"}),
    ("qr_redirect_prefilled.png", "danger", {"amount_prefilled", "embedded_url"}),
])
def test_qr_samples(client_for, sample, level, must_warn):
    with open(SAMPLES / sample, "rb") as fh:
        body = client_for("sita").post("/api/vision/qr/", {"image": fh, "language": "en"},
                                       format="multipart").json()
    assert body["level"] == level
    assert must_warn <= set(body["warnings"])


def test_unverified_qr_name_is_reported_as_a_claim(client_for):
    """A sticker carries the shop's name; the reply must not vouch for it."""
    with open(SAMPLES / "qr_sticker_tampered.png", "rb") as fh:
        body = client_for("sita").post("/api/vision/qr/", {"image": fh, "language": "en"},
                                       format="multipart").json()
    assert "could not confirm" in body["reply_text"]
    assert body["can_pay"] is False
