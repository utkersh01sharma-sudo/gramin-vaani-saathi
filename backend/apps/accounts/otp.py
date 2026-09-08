"""One-time-code issue, delivery, and verification.

Everything about the *security* of the flow lives here and is real:

* codes are generated with :mod:`secrets`, never :mod:`random`
* they are stored as password hashes, never in plaintext
* they expire, are single-use, and lock after a fixed number of wrong guesses
* re-sending is rate limited per destination, both by cooldown and per hour

What is *not* real is the last hop. This is a student capstone with no SMS
gateway and no transactional email provider, so :func:`deliver` writes the code
to the server console. Replacing it with a provider is a single function body;
nothing above it has to change. Keeping the boundary this narrow -- and saying
so out loud -- is the honest version of "OTP verification is implemented".

After a successful check the caller gets a signed, expiring *verification
token* rather than a server-side session flag. The registration request carries
it back, so a web worker holds no state between the two calls and the API can be
scaled by adding replicas -- the same reason the voice dialog round-trips its
pending action through the client.
"""
from __future__ import annotations

import logging
import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core import signing
from django.core.mail import send_mail
from django.utils import timezone

from .models import OtpChallenge

log = logging.getLogger(__name__)

VERIFICATION_SALT = "accounts.otp.verified.v1"

# Indian mobile numbers are ten digits starting 6-9. Accepting a +91 or leading
# 0 and stripping it is not leniency for its own sake: a user reading a number
# off a scrap of paper types it however it was written down.
_PHONE_RE = re.compile(r"^[6-9]\d{9}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")


class OtpError(Exception):
    """Something the user needs to be told about, in their own language.

    ``code`` is a stable machine string the PWA maps to a translated message;
    ``message`` is the English fallback for the API docs and the console.
    """

    def __init__(self, code: str, message: str, **extra):
        super().__init__(message)
        self.code = code
        self.message = message
        self.extra = extra


# ---------------------------------------------------------------- normalising
def normalise_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if not _PHONE_RE.match(digits):
        raise OtpError("bad_phone", "Enter a 10-digit Indian mobile number.")
    return digits


def normalise_email(value: str) -> str:
    email = (value or "").strip().lower()
    if not _EMAIL_RE.match(email):
        raise OtpError("bad_email", "Enter a valid email address.")
    return email


def normalise_destination(channel: str, value: str) -> str:
    if channel == OtpChallenge.Channel.PHONE:
        return normalise_phone(value)
    if channel == OtpChallenge.Channel.EMAIL:
        return normalise_email(value)
    raise OtpError("bad_channel", "Choose either a mobile number or an email address.")


# ---------------------------------------------------------------- issuing
def issue(channel: str, destination_raw: str, purpose: str = OtpChallenge.Purpose.REGISTER):
    """Create and deliver a challenge. Returns ``(challenge, code)``.

    The plaintext code comes back only so the caller can echo it in DEBUG. It is
    never persisted and never logged outside :func:`deliver`.
    """
    destination = normalise_destination(channel, destination_raw)
    _enforce_send_limits(destination)

    code = "".join(secrets.choice("0123456789") for _ in range(settings.OTP_LENGTH))

    challenge = OtpChallenge.objects.create(
        channel=channel,
        destination=destination,
        purpose=purpose,
        code_hash=make_password(code),
        expires_at=timezone.now() + timedelta(seconds=settings.OTP_TTL_SECONDS),
    )
    deliver(challenge, code)
    return challenge, code


def _enforce_send_limits(destination: str) -> None:
    """Two limits, guarding two different things.

    The cooldown stops a user hammering "resend" and racing themselves into a
    stale code. The hourly cap stops the endpoint being used to spam a number
    someone else owns -- which, with a real gateway attached, would cost money
    and goodwill.
    """
    now = timezone.now()
    recent = OtpChallenge.objects.filter(destination=destination).order_by("-created_at")

    latest = recent.first()
    if latest is not None:
        waited = (now - latest.created_at).total_seconds()
        if waited < settings.OTP_RESEND_COOLDOWN_SECONDS:
            raise OtpError(
                "cooldown",
                "A code was just sent. Please wait before asking for another.",
                retry_after=int(settings.OTP_RESEND_COOLDOWN_SECONDS - waited) + 1,
            )

    hour_ago = now - timedelta(hours=1)
    if recent.filter(created_at__gte=hour_ago).count() >= settings.OTP_MAX_PER_HOUR:
        raise OtpError(
            "too_many",
            "Too many codes requested for this number. Try again in an hour.",
            retry_after=3600,
        )


def deliver(challenge: OtpChallenge, code: str) -> None:
    """The one function that would change if a real provider were wired in.

    ``OTP_DELIVERY``:
      ``console`` -- log it (and, for email, hand it to EMAIL_BACKEND)
      ``silent``  -- deliver nowhere; for tests that read the challenge directly
    """
    if settings.OTP_DELIVERY == "silent":
        return

    body = (
        f"{code} is your Vaani Saathi verification code. "
        f"It is valid for {settings.OTP_TTL_SECONDS // 60} minutes. "
        "Never share it with anyone -- not even someone who says they are calling "
        "from your bank. A real bank never asks for this."
    )

    if challenge.channel == OtpChallenge.Channel.EMAIL:
        send_mail(
            subject="Your Vaani Saathi code",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[challenge.destination],
            fail_silently=True,
        )

    # Deliberately loud. With no carrier attached this line *is* the delivery
    # channel, and a demo needs to find it in the runserver output.
    log.info(
        "OTP [%s -> %s] %s  (expires in %ss)",
        challenge.channel,
        challenge.masked_destination(),
        code,
        settings.OTP_TTL_SECONDS,
    )


# ---------------------------------------------------------------- verifying
def verify(challenge_id, code: str) -> OtpChallenge:
    """Check a code and consume the challenge. Raises :class:`OtpError`."""
    try:
        challenge = OtpChallenge.objects.get(pk=challenge_id)
    except (OtpChallenge.DoesNotExist, ValueError, TypeError):
        raise OtpError("not_found", "That code request has expired. Please start again.")

    if challenge.consumed_at is not None:
        raise OtpError("already_used", "That code has already been used.")
    if challenge.is_expired():
        raise OtpError("expired", "That code has expired. Ask for a new one.")
    if challenge.is_locked():
        raise OtpError("locked", "Too many wrong tries. Ask for a new code.")

    submitted = re.sub(r"\D", "", code or "")
    if not check_password(submitted, challenge.code_hash):
        # Count the attempt before returning, or the limit means nothing.
        challenge.attempts += 1
        challenge.save(update_fields=["attempts"])
        raise OtpError(
            "wrong_code",
            "That code is not right.",
            attempts_remaining=challenge.attempts_remaining(),
        )

    challenge.consumed_at = timezone.now()
    challenge.save(update_fields=["consumed_at"])
    return challenge


def make_verification_token(challenge: OtpChallenge) -> str:
    """Proof that a destination was verified: signed, and self-expiring."""
    return signing.dumps(
        {
            "cid": str(challenge.id),
            "channel": challenge.channel,
            "destination": challenge.destination,
            "purpose": challenge.purpose,
        },
        salt=VERIFICATION_SALT,
    )


def read_verification_token(token: str, purpose: str = OtpChallenge.Purpose.REGISTER) -> dict:
    try:
        payload = signing.loads(
            token, salt=VERIFICATION_SALT, max_age=settings.OTP_VERIFICATION_TTL_SECONDS
        )
    except signing.SignatureExpired:
        raise OtpError("verification_expired", "Verification timed out. Please verify again.")
    except signing.BadSignature:
        raise OtpError("verification_invalid", "Verification failed. Please start again.")

    if payload.get("purpose") != purpose:
        raise OtpError("verification_invalid", "Verification failed. Please start again.")
    return payload
