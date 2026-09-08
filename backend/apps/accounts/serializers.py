from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import Contact, User, UserProfile


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "phone", "first_name", "last_name"]
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


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=64)
    phone = serializers.CharField(max_length=15)
    password = serializers.CharField(write_only=True, min_length=4)
    language = serializers.ChoiceField(
        choices=["hi", "en", "ta", "te"], default="hi", required=False
    )
    literacy_level = serializers.ChoiceField(
        choices=["none", "basic", "full"], default="none", required=False
    )

    def validate_username(self, value: str) -> str:
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("That username is taken.")
        return value

    def validate_phone(self, value: str) -> str:
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) != 10:
            raise serializers.ValidationError("Enter a 10-digit mobile number.")
        if User.objects.filter(phone=digits).exists():
            raise serializers.ValidationError("That phone number is already registered.")
        return digits


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs: dict) -> dict:
        user = authenticate(username=attrs["username"], password=attrs["password"])
        if user is None:
            raise serializers.ValidationError("Wrong username or password.")
        attrs["user"] = user
        return attrs
