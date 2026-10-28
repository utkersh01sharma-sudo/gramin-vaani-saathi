import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from ai import registry


@pytest.fixture
def seeded(db):
    """The four demo users, their sandbox accounts and contacts."""
    call_command("seed_demo", verbosity=0)


@pytest.fixture
def sita(seeded):
    from apps.accounts.models import User

    return User.objects.get(username="sita")


@pytest.fixture
def client_for(seeded):
    def make(username: str = "sita") -> APIClient:
        client = APIClient()
        token = client.post("/api/accounts/login/", {"username": username, "password": "demo1234"},
                            format="json").json()["token"]
        client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        return client

    return make


@pytest.fixture
def rules_only_scam(settings, tmp_path):
    """ScamNet without the transformer: fast, deterministic, no GPU in CI."""
    settings.SCAM_MODEL_PATH = str(tmp_path)
    registry.get_scam.cache_clear()
    yield
    registry.get_scam.cache_clear()
