"""User identity and the profile that drives both UI adaptation and scheme eligibility.

The profile fields are deliberately the *exact* inputs the government-scheme
eligibility engine needs (see apps/schemes/engine.py), so a user answers the
onboarding questions once and never re-enters them per scheme.
"""
import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


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
    """Phone is the primary handle; email is the fallback for people who have one.

    Both are nullable and unique. Rural users overwhelmingly sign up with a
    mobile number, but a shopkeeper or a student may only have email, and
    forcing a placeholder phone number would corrupt the one field the OTP
    channel actually depends on. Empty strings are normalised to NULL by
    :meth:`save` so the unique constraint does not collide on "".
    """

    phone = models.CharField(
        max_length=15, unique=True, db_index=True, null=True, blank=True
    )
    email = models.EmailField(unique=True, null=True, blank=True)

    # Which channel the account was verified through, and when. Kept because an
    # account created before OTP was introduced is legitimately unverified, and
    # the difference should be visible rather than assumed.
    verified_channel = models.CharField(max_length=8, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "username"

    def save(self, *args, **kwargs):
        # UNIQUE treats every "" as equal but every NULL as distinct. Two users
        # without email must both be storable, so blank becomes NULL here.
        self.phone = self.phone or None
        self.email = self.email or None
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.username} ({self.phone or self.email or 'no contact'})"


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


class OtpChallenge(models.Model):
    """A one-time code sent to a phone or an email, and the state of its use.

    SAFETY / SCOPE: this project does not integrate a real SMS gateway or a
    transactional email provider. ``OTP_DELIVERY`` decides where the code
    actually goes -- in this build it goes to the server console (and, for the
    email channel, through Django's console email backend). The verification
    *logic* is real: codes are hashed at rest, expire, are single-use, and are
    rate limited. What is simulated is only the last hop, the carrier.

    The code is stored as a password hash, never in plaintext. A student project
    database ends up in screenshots, on USB sticks, and in a GitHub repo; a
    column of live OTPs is exactly the kind of thing that should not be sitting
    in any of those places.
    """

    class Channel(models.TextChoices):
        PHONE = "phone", "Mobile number"
        EMAIL = "email", "Email address"

    class Purpose(models.TextChoices):
        REGISTER = "register", "Create a new account"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.CharField(max_length=8, choices=Channel.choices)
    destination = models.CharField(max_length=254, db_index=True)
    purpose = models.CharField(
        max_length=16, choices=Purpose.choices, default=Purpose.REGISTER
    )

    code_hash = models.CharField(max_length=128)
    attempts = models.PositiveSmallIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["destination", "created_at"])]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"OTP<{self.channel}:{self.masked_destination()}>"

    # ---------------------------------------------------------------- state
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def is_locked(self) -> bool:
        return self.attempts >= settings.OTP_MAX_ATTEMPTS

    def is_usable(self) -> bool:
        return self.consumed_at is None and not self.is_expired() and not self.is_locked()

    def attempts_remaining(self) -> int:
        return max(0, settings.OTP_MAX_ATTEMPTS - self.attempts)

    def seconds_remaining(self) -> int:
        return max(0, int((self.expires_at - timezone.now()).total_seconds()))

    # ---------------------------------------------------------------- display
    def masked_destination(self) -> str:
        """What the UI is allowed to echo back.

        The user needs to recognise the destination to catch a typo, without the
        full value being readable over their shoulder or from a screenshot.
        """
        value = self.destination
        if self.channel == self.Channel.EMAIL:
            local, _, domain = value.partition("@")
            head = local[:2] if len(local) > 3 else local[:1]
            return f"{head}{'*' * max(3, len(local) - len(head))}@{domain}"
        return f"{'*' * max(0, len(value) - 4)}{value[-4:]}"
