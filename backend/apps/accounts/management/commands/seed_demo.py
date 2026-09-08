# -*- coding: utf-8 -*-
"""Create the demo households the PWA signs into.

    python backend/manage.py seed_demo

Four sandbox identities: three villagers who pay each other, plus one shop so
the QR flow has a merchant to resolve to. Names are stored in both Latin and
local script because ``Contact.name_local`` doubles as the gazetteer that
ai/local/slots.py matches spoken payee names against.

Idempotent -- re-running tops the accounts back up and leaves the ledger alone.
The password is a fixed sandbox string; these accounts hold play money in a
local database and exist only so a demo does not open with a signup form.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Contact, User, UserProfile
from apps.banking.models import SandboxAccount

DEMO_PASSWORD = "demo1234"

PEOPLE = [
    {
        "username": "sita", "first_name": "Sita", "phone": "9000000001",
        "name_local": {"hi": "सीता", "ta": "சீதா", "te": "సీత"},
        "language": "hi", "balance": "4250.00",
        "profile": {
            "literacy_level": "none", "age": 34, "gender": "F", "state": "Bihar",
            "district": "Gaya", "occupation": "farmer", "annual_income": 84000,
            "land_holding_acres": "1.20", "has_bank_account": True, "is_bpl": True,
            "household_size": 5,
        },
    },
    {
        "username": "ramesh", "first_name": "Ramesh", "phone": "9000000002",
        "name_local": {"hi": "रमेश", "ta": "ரமேஷ்", "te": "రమేష్"},
        "language": "hi", "balance": "1800.00",
        "profile": {
            "literacy_level": "basic", "age": 41, "gender": "M", "state": "Bihar",
            "district": "Gaya", "occupation": "labourer", "annual_income": 96000,
            "land_holding_acres": "0.00", "has_bank_account": True, "is_bpl": True,
            "household_size": 4,
        },
    },
    {
        "username": "lakshmi", "first_name": "Lakshmi", "phone": "9000000003",
        "name_local": {"hi": "लक्ष्मी", "ta": "லட்சுமி", "te": "లక్ష్మి"},
        "language": "te", "balance": "6120.00",
        "profile": {
            "literacy_level": "basic", "age": 29, "gender": "F", "state": "Telangana",
            "district": "Warangal", "occupation": "self_employed", "annual_income": 132000,
            "land_holding_acres": "0.50", "has_bank_account": True, "is_bpl": False,
            "household_size": 3,
        },
    },
    {
        "username": "ramkirana", "first_name": "Ram Kirana Store", "phone": "9000000004",
        "name_local": {"hi": "राम किराना स्टोर", "ta": "ராம் கிரானா ஸ்டோர்", "te": "రామ్ కిరాణా స్టోర్"},
        "language": "hi", "balance": "15400.00",
        "profile": {
            "literacy_level": "full", "age": 46, "gender": "M", "state": "Bihar",
            "district": "Gaya", "occupation": "self_employed", "annual_income": 240000,
            "land_holding_acres": "0.00", "has_bank_account": True, "is_bpl": False,
            "household_size": 6,
        },
    },
]

# Who appears in whose contact list. Everyone can pay the shop.
CONTACT_MAP = {
    "sita": ["ramesh", "lakshmi", "ramkirana"],
    "ramesh": ["sita", "lakshmi", "ramkirana"],
    "lakshmi": ["sita", "ramesh", "ramkirana"],
    "ramkirana": ["sita", "ramesh", "lakshmi"],
}


class Command(BaseCommand):
    help = "Create or refresh the four sandbox demo accounts."

    @transaction.atomic
    def handle(self, *args, **options):
        users: dict[str, User] = {}

        for spec in PEOPLE:
            user, created = User.objects.get_or_create(
                username=spec["username"],
                defaults={"phone": spec["phone"], "first_name": spec["first_name"]},
            )
            user.first_name = spec["first_name"]
            user.phone = spec["phone"]
            user.set_password(DEMO_PASSWORD)
            user.save()
            users[spec["username"]] = user

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.language = spec["language"]
            for field, value in spec["profile"].items():
                setattr(profile, field, value)
            profile.save()

            account, _ = SandboxAccount.objects.get_or_create(
                user=user,
                defaults={
                    "account_number": f"9{spec['phone'][1:]}0000",
                    "vpa": f"{spec['username']}@sandbox",
                },
            )
            # Top the play money back up on every run so a demo always starts
            # from the same figures, whatever last night's rehearsal did.
            account.balance = Decimal(spec["balance"])
            account.save(update_fields=["balance"])

            self.stdout.write(
                f"  {'created' if created else 'refreshed'} {user.username} "
                f"({account.vpa}) balance {account.balance}"
            )

        by_username = {spec["username"]: spec for spec in PEOPLE}
        for owner, others in CONTACT_MAP.items():
            user = users[owner]
            owner_lang = by_username[owner]["language"]
            for other in others:
                spec = by_username[other]
                Contact.objects.update_or_create(
                    user=user,
                    vpa=f"{other}@sandbox",
                    defaults={
                        "name": spec["first_name"],
                        # Rendered in the payer's own script, since that is the
                        # script their speech will be transcribed into.
                        "name_local": spec["name_local"].get(owner_lang, spec["first_name"]),
                    },
                )

        self.stdout.write(self.style.SUCCESS(
            f"\nSeeded {len(PEOPLE)} sandbox accounts. Password for all of them: {DEMO_PASSWORD}"
        ))
        self.stdout.write("These are simulated accounts holding play money. No real bank is involved.")
