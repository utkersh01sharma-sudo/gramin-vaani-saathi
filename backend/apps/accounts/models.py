"""User identity and the profile that drives both UI adaptation and scheme eligibility.

The profile fields are deliberately the *exact* inputs the government-scheme
eligibility engine needs (see apps/schemes/engine.py), so a user answers the
onboarding questions once and never re-enters them per scheme.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class Language(models.TextChoices):
    HINDI = "hi", "हिन्दी"
    ENGLISH = "en", "English"
    TAMIL = "ta", "தமிழ்"
    TELUGU = "te", "తెలుగు"


class LiteracyLevel(models.TextChoices):
    """Drives how much text the UI shows. NON_LITERATE = icons + audio only."""

    NON_LITERATE = "none", "Cannot read"
    BASIC = "basic", "Can read simple words"
    COMFORTABLE = "full", "Reads comfortably"


class Gender(models.TextChoices):
    FEMALE = "F", "Female"
    MALE = "M", "Male"
    OTHER = "O", "Other"


class Occupation(models.TextChoices):
    FARMER = "farmer", "Farmer"
    LABOURER = "labourer", "Daily wage labourer"
    SELF_EMPLOYED = "self_employed", "Small business / self-employed"
    HOMEMAKER = "homemaker", "Homemaker"
    STUDENT = "student", "Student"
    OTHER = "other", "Other"


class User(AbstractUser):
    """Phone number is the real identifier; rural users rarely have email."""

    phone = models.CharField(max_length=15, unique=True, db_index=True)

    USERNAME_FIELD = "username"

    def __str__(self) -> str:
        return f"{self.username} ({self.phone})"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    # --- UI adaptation ---
    language = models.CharField(max_length=2, choices=Language.choices, default=Language.HINDI)
    literacy_level = models.CharField(
        max_length=8, choices=LiteracyLevel.choices, default=LiteracyLevel.NON_LITERATE
    )

    # --- Scheme eligibility inputs ---
    age = models.PositiveSmallIntegerField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=Gender.choices, blank=True)
    state = models.CharField(max_length=64, blank=True)
    district = models.CharField(max_length=64, blank=True)
    occupation = models.CharField(max_length=16, choices=Occupation.choices, blank=True)
    annual_income = models.PositiveIntegerField(
        null=True, blank=True, help_text="Household annual income in INR"
    )
    land_holding_acres = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    has_bank_account = models.BooleanField(default=True)
    is_bpl = models.BooleanField(default=False, help_text="Below Poverty Line card holder")
    household_size = models.PositiveSmallIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Profile<{self.user.username}>"

    def eligibility_facts(self) -> dict:
        """Flatten the profile into the fact dict the scheme rule engine evaluates."""
        return {
            "age": self.age,
            "gender": self.gender,
            "state": self.state,
            "occupation": self.occupation,
            "annual_income": self.annual_income,
            "land_holding_acres": (
                float(self.land_holding_acres) if self.land_holding_acres is not None else None
            ),
            "has_bank_account": self.has_bank_account,
            "is_bpl": self.is_bpl,
            "household_size": self.household_size,
        }


class Contact(models.Model):
    """Payee address book. Doubles as the gazetteer for payee-name slot filling."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="contacts")
    name = models.CharField(max_length=64)
    name_local = models.CharField(
        max_length=64, blank=True, help_text="Name in the user's own script, for ASR matching"
    )
    vpa = models.CharField(max_length=64, help_text="Simulated UPI VPA, e.g. ramesh@sandbox")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "vpa")]

    def __str__(self) -> str:
        return f"{self.name} <{self.vpa}>"
