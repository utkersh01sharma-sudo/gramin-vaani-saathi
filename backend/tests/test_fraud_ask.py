# -*- coding: utf-8 -*-
"""The fraud-question search: reviewed answers, and an honest "no answer"."""
from apps.fraud import knowledge
from apps.voice.dialog import _looks_like_question


def test_knowledge_base_validates_in_four_languages():
    entries = knowledge.load_entries()
    assert len(entries) >= 25
    assert all(e["q"][l] and e["a"][l] for e in entries for l in ("hi", "en", "ta", "te"))
    # Only official, safe link schemes.
    assert all(link["href"].startswith(("tel:", "https://")) for e in entries for link in e.get("links", []))


def test_ask_answers_an_otp_question(client_for, monkeypatch):
    from apps.fraud import views

    monkeypatch.setattr(views, "get_embedder", lambda: None)   # keyword mode: fast, no model
    body = client_for("sita").post("/api/fraud/ask/", {"text": "should I share my OTP with the bank?",
                                                      "language": "en"}, format="json").json()
    assert body["answered"] and body["best"]["id"] == "share-otp"
    assert "never" in body["best"]["answer"].lower()


def test_off_topic_question_gets_no_answer(client_for, monkeypatch):
    from apps.fraud import views

    monkeypatch.setattr(views, "get_embedder", lambda: None)
    body = client_for("sita").post("/api/fraud/ask/", {"text": "what is the weather tomorrow",
                                                      "language": "en"}, format="json").json()
    assert body["answered"] is False and body["best"] is None


def test_suggested_questions_are_localised(client_for):
    hi = client_for("sita").get("/api/fraud/questions/?lang=hi").json()["results"]
    assert hi and all(q["question"] for q in hi)


def test_question_detection_for_voice():
    assert _looks_like_question("OTP बताना चाहिए क्या")
    assert _looks_like_question("should I install anydesk?")
    assert _looks_like_question("எப்படி மோசடியைக் கண்டுபிடிப்பது")
    # A read-out scam message with a question mark in the middle stays a message.
    assert not _looks_like_question("Your SBI account will be blocked? Update KYC at bit.ly/x today")
