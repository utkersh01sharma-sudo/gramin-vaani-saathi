"""AI_BACKEND=remote: the client contract and its degrade-don't-break fallback.

These do not start the model server (that needs the GPU artifacts); they stub
the single HTTP call so the adapter logic is tested on its own.
"""
from ai.remote import client


def test_remote_nlu_parses_server_response(monkeypatch):
    monkeypatch.setattr(client, "_post_json", lambda path, payload: {
        "intent": "check_balance", "confidence": 0.81, "slots": {}, "all_scores": {},
        "backend": "muril_intent"})
    nlu = client.RemoteNLU()
    pred = nlu.predict("mera balance batao", "hi")
    assert pred.intent == "check_balance" and nlu.active_backend == "remote:muril_intent"


def _down(*_args, **_kwargs):
    raise client.RemoteError("connection refused")


def test_remote_nlu_falls_back_to_keywords(monkeypatch):
    monkeypatch.setattr(client, "_post_json", _down)
    nlu = client.RemoteNLU()
    pred = nlu.predict("what is my balance", "en")
    assert pred.intent == "check_balance"
    assert "remote down" in nlu.active_backend


def test_remote_scam_falls_back_to_rules(monkeypatch):
    monkeypatch.setattr(client, "_post_json", _down)
    scam = client.RemoteScam()
    verdict = scam.classify("Share the OTP immediately or your account will be blocked", "en")
    assert verdict.label in {"suspicious", "scam"} and verdict.reasons
    assert scam.explain(verdict, "hi")["headline"]
