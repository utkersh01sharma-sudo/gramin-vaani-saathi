import secrets

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.banking.models import SandboxAccount

from .models import Contact, User, UserProfile
from .serializers import (
    ContactSerializer,
    LoginSerializer,
    RegisterSerializer,
    UserProfileSerializer,
    UserSerializer,
)


def _new_sandbox_account(user: User) -> SandboxAccount:
    """Open a play-money account. Seeded with a small opening balance so a new
    user can try a transfer immediately without a top-up flow."""
    return SandboxAccount.objects.create(
        user=user,
        account_number=f"9{secrets.randbelow(10**11):011d}",
        vpa=f"{user.username.lower()}@sandbox",
        balance=2000,
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

        user = User.objects.create_user(
            username=data["username"],
            phone=data["phone"],
            password=data["password"],
        )
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


@extend_schema(tags=["accounts"])
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
