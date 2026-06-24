# auth_service/tests/test_secrets.py
"""Auth secret resolver: env fallback + resource-override precedence (no GCP)."""
from auth_service.app.secrets import resolve_secret


def test_env_fallback(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "from-env")
    monkeypatch.delenv("JWT_SECRET_SECRET_RESOURCE", raising=False)
    monkeypatch.setenv("SECRETS_BACKEND", "env")
    assert resolve_secret("JWT_SECRET", "jwt-secret") == "from-env"


def test_default_when_unset(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("JWT_SECRET_SECRET_RESOURCE", raising=False)
    monkeypatch.setenv("SECRETS_BACKEND", "env")
    assert resolve_secret("JWT_SECRET", "jwt-secret", default="fallback") == "fallback"


def test_bad_resource_falls_back_to_env(monkeypatch):
    # A resource is set but the GCP client import/fetch fails -> env is used.
    monkeypatch.setenv("JWT_SECRET", "from-env")
    monkeypatch.setenv("JWT_SECRET_SECRET_RESOURCE", "projects/x/secrets/y/versions/1")
    assert resolve_secret("JWT_SECRET", "jwt-secret") == "from-env"
