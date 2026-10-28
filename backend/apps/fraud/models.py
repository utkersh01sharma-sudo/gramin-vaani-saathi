"""Scam checks and scam reports.

A check is the app scoring a message someone pasted or read aloud. A report is
a person saying "this happened to me". They are separate tables because they
answer different questions: checks measure the model in the field (how often
does it say scam, and does the user then report anyway?), reports are the
start of a complaint the user still has to take to 1930 / cybercrime.gov.in --
the app cannot file one for them and never says it has.
"""
from django.conf import settings
from django.db import models


class ScamCheck(models.Model):
    class Label(models.TextChoices):
        SAFE = "safe", "Safe"
        SUSPICIOUS = "suspicious", "Suspicious"
        SCAM = "scam", "Scam"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="scam_checks")
    text = models.TextField()
    language = models.CharField(max_length=2)
    label = models.CharField(max_length=10, choices=Label.choices)
    score = models.FloatField()
    model_score = models.FloatField(default=0)
    rule_score = models.FloatField(default=0)
    reasons = models.JSONField(default=list)
    backend = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.label} ({self.score:.2f}) {self.text[:40]}"


class ScamReport(models.Model):
    class Kind(models.TextChoices):
        MONEY_LOST = "money_lost", "Money was taken"
        SHARED_DETAILS = "shared_details", "I shared my OTP / PIN / card"
        MESSAGE_ONLY = "message_only", "I received a fraud message"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="scam_reports")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    description = models.TextField(blank=True)
    message_text = models.TextField(blank=True)
    amount_lost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
