# execution_engine/tests/test_secrets.py
"""Offline tests for secret resolution precedence (no GCP, no network)."""
import os

from execution_engine.app.secrets import SecretResolver


def test_env_fallback(monkeypatch):
    monkeypatch.setenv("MY_KEY", "from-env")
    r = SecretResolver(project_id="proj", backend="env")
    assert r.get("MY_KEY", secret_id="my-key") == "from-env"


def test_env_default_when_unset(monkeypatch):
    monkeypatch.delenv("MISSING_KEY", raising=False)
    r = SecretResolver(project_id="proj", backend="env")
    assert r.get("MISSING_KEY", default="fallback") == "fallback"


def test_resource_override_takes_precedence(monkeypatch):
    monkeypatch.setenv("MY_KEY", "from-env")
    monkeypatch.setenv("MY_KEY_SECRET_RESOURCE", "projects/p/secrets/s/versions/1")
    r = SecretResolver(project_id="proj", backend="env")
    # Stub the fetch so we don't hit GCP; prove the resource path is used.
    monkeypatch.setattr(r, "_fetch", lambda res: f"value-of:{res}")
    assert r.get("MY_KEY", secret_id="my-key") == "value-of:projects/p/secrets/s/versions/1"


def test_gcp_convention_used_when_backend_gcp(monkeypatch):
    monkeypatch.setenv("MY_KEY", "from-env")
    monkeypatch.delenv("MY_KEY_SECRET_RESOURCE", raising=False)
    r = SecretResolver(project_id="proj", backend="gcp")
    seen = {}
    def fake_fetch(res):
        seen["res"] = res
        return "from-gcp"
    monkeypatch.setattr(r, "_fetch", fake_fetch)
    assert r.get("MY_KEY", secret_id="binance-api-key") == "from-gcp"
    assert seen["res"] == "projects/proj/secrets/binance-api-key/versions/latest"


def test_falls_back_to_env_when_fetch_fails(monkeypatch):
    monkeypatch.setenv("MY_KEY", "from-env")
    r = SecretResolver(project_id="proj", backend="gcp")
    monkeypatch.setattr(r, "_fetch", lambda res: None)  # simulate fetch failure
    assert r.get("MY_KEY", secret_id="my-key") == "from-env"
