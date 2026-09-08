from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import Contact, OtpChallenge, User, UserProfile


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "phone", "email", "first_name", "last_name"]
        read_only_fields = ["id"]


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            "language",
            "literacy_level",
            "age",
            "gender",
            "state",
            "district",
            "occupation",
            "annual_income",
            "land_holding_acres",
            "has_bank_account",
            "is_bpl",
            "household_size",
        ]


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ["id", "name", "name_local", "vpa"]
        read_only_fields = ["id"]


class OtpRequestSerializer(serializers.Serializer):
    """Ask for a code. One of phone / email, chosen by ``channel``."""

    channel = serializers.ChoiceField(choices=OtpChallenge.Channel.choices)
    destination = serializers.CharField(max_length=254)


class OtpVerifySerializer(serializers.Serializer):
    challenge_id = serializers.CharField()
    code = serializers.CharField(max_length=16)


class RegisterSerializer(serializers.Serializer):
    """Create an account against a destination that has already been verified.

    Phone and email are deliberately *not* accepted here. They come out of the
    signed verification token, so a client cannot verify one number and register
    a different one.
    """

    verification_token = serializers.CharField()
    display_name = serializers.CharField(max_length=64)
    password = serializers.CharField(write_only=True, min_length=4)
    username = serializers.CharField(max_length=64, required=False, allow_blank=True)
    language = serializers.ChoiceField(
        choices=["hi", "en", "ta", "te"], default="hi", required=False
    )
    literacy_level = serializers.ChoiceField(
        choices=["none", "basic", "full"], default="none", required=False
    )

    def validate_username(self, value: str) -> str:
        value = (value or "").strip()
        if value and User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("That name is taken.")
        return value


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs: dict) -> dict:
        user = authenticate(username=attrs["username"], password=attrs["password"])
        if user is None:
            raise serializers.ValidationError("Wrong username or password.")
        attrs["user"] = user
        return attrs
