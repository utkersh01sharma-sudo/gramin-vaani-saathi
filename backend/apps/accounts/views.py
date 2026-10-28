import re
import secrets
import unicodedata
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.banking.models import SandboxAccount

from . import otp as otp_service
from .models import Contact, OtpChallenge, User, UserProfile
from .serializers import (
    ContactSerializer,
    LoginSerializer,
    OtpRequestSerializer,
    OtpVerifySerializer,
    RegisterSerializer,
    UserProfileSerializer,
    UserSerializer,
)


def _otp_error_response(err: otp_service.OtpError) -> Response:
    """Machine-readable first, prose second.

    The PWA has to say this in Hindi, Tamil, or Telugu, so it switches on
    ``error`` and shows ``detail`` only when it meets a code it does not know.
    """
    status_code = (
        status.HTTP_429_TOO_MANY_REQUESTS
        if err.code in {"cooldown", "too_many"}
        else status.HTTP_400_BAD_REQUEST
    )
    return Response({"error": err.code, "detail": err.message, **err.extra}, status=status_code)


def _unique_handle(*seeds: str) -> str:
    """Derive a free username that is also safe as the VPA local part.

    People pick a display name in their own script; the ledger needs an ASCII
    handle, and that handle becomes the VPA the payee sees. Transliterating
    Devanagari or Telugu properly is a project of its own, so the seeds are
    tried in order and the first that survives ASCII-folding wins -- a name in
    Latin script, then the email local part, then the phone number. Only if all
    of those fail does it fall back to a numeric handle, which is ugly but at
    least is not mojibake.
    """
    base = ""
    for seed in seeds:
        folded = unicodedata.normalize("NFKD", seed or "").encode("ascii", "ignore").decode()
        candidate_base = re.sub(r"[^a-z0-9]", "", folded.lower())[:20]
        if len(candidate_base) >= 3:
            base = candidate_base
            break
    if not base:
        base = "user%04d" % secrets.randbelow(10000)

    candidate = base
    for _ in range(50):
        taken = (
            User.objects.filter(username__iexact=candidate).exists()
            or SandboxAccount.objects.filter(vpa=candidate + "@sandbox").exists()
        )
        if not taken:
            return candidate
        candidate = "%s%04d" % (base, secrets.randbelow(10000))
    raise RuntimeError("could not allocate a free username")


def _new_sandbox_account(user: User) -> SandboxAccount:
    """Open a play-money account. Seeded with a small opening balance so a new
    user can try a transfer immediately without a top-up flow."""
    return SandboxAccount.objects.create(
        user=user,
        account_number=f"9{secrets.randbelow(10**11):011d}",
        vpa=f"{user.username.lower()}@sandbox",
        balance=Decimal("2000.00"),
    )


@extend_schema(tags=["accounts"])
class OtpRequestView(APIView):
    """Send a one-time code to a phone number or an email address.

    SCOPE: no SMS gateway or email provider is integrated in this project. The
    code is written to the server console (see apps/accounts/otp.py), and in
    DEBUG it is echoed back as ``dev_code`` so the signup flow can be walked
    through without a carrier. Everything else -- hashing at rest, expiry,
    single use, attempt limits, rate limiting -- behaves as it would in
    production.
    """

    permission_classes = [AllowAny]
    serializer_class = OtpRequestSerializer

    def post(self, request):
        serializer = OtpRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        channel = serializer.validated_data["channel"]
        raw = serializer.validated_data["destination"]

        try:
            destination = otp_service.normalise_destination(channel, raw)
        except otp_service.OtpError as err:
            return _otp_error_response(err)

        # Refuse here rather than after the code has been typed. Being told
        # "already registered" at the end of a signup flow is a bad five
        # minutes, especially for someone who reads slowly.
        field = "phone" if channel == OtpChallenge.Channel.PHONE else "email"
        if User.objects.filter(**{field: destination}).exists():
            return Response(
                {
                    "error": "already_registered",
                    "detail": "That contact already has an account. Please sign in instead.",
                },
                status=status.HTTP_409_CONFLICT,
            )

        try:
            challenge, code = otp_service.issue(channel, destination)
        except otp_service.OtpError as err:
            return _otp_error_response(err)

        payload = {
            "challenge_id": str(challenge.id),
            "channel": challenge.channel,
            "destination_masked": challenge.masked_destination(),
            "expires_in": challenge.seconds_remaining(),
            "code_length": settings.OTP_LENGTH,
            "resend_in": settings.OTP_RESEND_COOLDOWN_SECONDS,
            "delivery": settings.OTP_DELIVERY,
        }
        if settings.OTP_ECHO_IN_RESPONSE:
            payload["dev_code"] = code
        return Response(payload, status=status.HTTP_201_CREATED)


@extend_schema(tags=["accounts"])
class OtpVerifyView(APIView):
    """Exchange a correct code for a short-lived signed verification token."""

    permission_classes = [AllowAny]
    serializer_class = OtpVerifySerializer

    def post(self, request):
        serializer = OtpVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            challenge = otp_service.verify(
                serializer.validated_data["challenge_id"],
                serializer.validated_data["code"],
            )
        except otp_service.OtpError as err:
            return _otp_error_response(err)

        return Response(
            {
                "verification_token": otp_service.make_verification_token(challenge),
                "channel": challenge.channel,
                "destination_masked": challenge.masked_destination(),
                "expires_in": settings.OTP_VERIFICATION_TTL_SECONDS,
            }
        )


@extend_schema(tags=["accounts"])
class RegisterView(APIView):
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    @transaction.atomic
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            verified = otp_service.read_verification_token(data["verification_token"])
        except otp_service.OtpError as err:
            return _otp_error_response(err)

        # Contact details come out of the signed token, never out of the request
        # body, so verifying one number and registering a different one is not
        # a thing a client can do.
        channel = verified["channel"]
        destination = verified["destination"]
        field = "phone" if channel == OtpChallenge.Channel.PHONE else "email"

        if User.objects.filter(**{field: destination}).exists():
            return Response(
                {
                    "error": "already_registered",
                    "detail": "That contact already has an account. Please sign in instead.",
                },
                status=status.HTTP_409_CONFLICT,
            )

        display_name = data["display_name"].strip()
        # Seeded from the name first, then the contact detail, so the VPA a payee
        # ends up seeing is recognisable rather than a random number.
        email_local = destination.split("@")[0] if channel == OtpChallenge.Channel.EMAIL else ""
        phone_seed = destination if channel == OtpChallenge.Channel.PHONE else ""
        username = data.get("username") or _unique_handle(display_name, email_local, phone_seed)

        user = User.objects.create_user(
            username=username,
            password=data["password"],
            first_name=display_name[:150],
            **{field: destination},
        )
        user.verified_channel = channel
        user.verified_at = timezone.now()
        user.save(update_fields=["verified_channel", "verified_at"])

        profile = UserProfile.objects.create(
            user=user,
            language=data.get("language", "hi"),
            literacy_level=data.get("literacy_level", "none"),
        )
        account = _new_sandbox_account(user)
        token, _ = Token.objects.get_or_create(user=user)

        return Response(
            {
                "token": token.key,
                "user": UserSerializer(user).data,
                "profile": UserProfileSerializer(profile).data,
                "account": {"vpa": account.vpa, "balance": str(account.balance)},
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["accounts"])
class LoginView(APIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        profile, _ = UserProfile.objects.get_or_create(user=user)
        return Response(
            {
                "token": token.key,
                "user": UserSerializer(user).data,
                "profile": UserProfileSerializer(profile).data,
            }
        )


@extend_schema(tags=["accounts"], responses=OpenApiTypes.OBJECT)
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        profile, _ = UserProfile.objects.get_or_create(user=user)
        account = SandboxAccount.objects.filter(user=user).first()
        return Response(
            {
                "user": UserSerializer(user).data,
                "profile": UserProfileSerializer(profile).data,
                "account": (
                    {
                        "vpa": account.vpa,
                        "masked_account_number": account.masked_account_number(),
                        "balance": str(account.balance),
                        "bank_name": account.bank_name,
                    }
                    if account
                    else None
                ),
                "contacts": ContactSerializer(user.contacts.all(), many=True).data,
            }
        )


@extend_schema(tags=["accounts"])
class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    def patch(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"profile": serializer.data})


@extend_schema(tags=["accounts"])
class ContactListView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ContactSerializer

    def get(self, request):
        return Response(
            {"results": ContactSerializer(request.user.contacts.all(), many=True).data}
        )

    def post(self, request):
        serializer = ContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contact = Contact.objects.create(user=request.user, **serializer.validated_data)
        return Response(ContactSerializer(contact).data, status=status.HTTP_201_CREATED)
