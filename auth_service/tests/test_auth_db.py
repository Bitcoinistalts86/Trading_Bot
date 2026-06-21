# auth_service/tests/test_auth_db.py
"""End-to-end auth tests against a temp SQLite DB (no GCP, no network)."""
import os
import tempfile

import pytest

# Point the service at a throwaway SQLite file BEFORE importing the app.
_DB = os.path.join(tempfile.mkdtemp(), "test_auth.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ["JWT_SECRET"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402
from auth_service.app.main import app  # noqa: E402
from auth_service.app.db import init_db  # noqa: E402
from auth_service.app.seed import create_admin  # noqa: E402

init_db()
client = TestClient(app)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_signup_login_me_flow():
    r = client.post("/signup", json={"email": "u1@example.com", "password": "pw123456"})
    assert r.status_code == 200, r.text
    tokens = r.json()
    assert tokens["access_token"] and tokens["refresh_token"]

    me = client.get("/me", headers=_auth(tokens["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == "u1@example.com"
    assert me.json()["role"] == "USER"


def test_duplicate_email_rejected():
    client.post("/signup", json={"email": "dup@example.com", "password": "pw123456"})
    r = client.post("/signup", json={"email": "dup@example.com", "password": "pw123456"})
    assert r.status_code == 400


def test_wrong_password_rejected():
    client.post("/signup", json={"email": "u2@example.com", "password": "right-pass"})
    r = client.post("/login", json={"email": "u2@example.com", "password": "wrong-pass"})
    assert r.status_code == 400


def test_refresh_issues_new_access_token():
    s = client.post("/signup", json={"email": "u3@example.com", "password": "pw123456"}).json()
    r = client.post("/refresh", json={"refresh_token": s["refresh_token"]})
    assert r.status_code == 200
    assert r.json()["access_token"]
    # An access token must not be usable as a refresh token.
    bad = client.post("/refresh", json={"refresh_token": s["access_token"]})
    assert bad.status_code == 401


def test_admin_endpoints_require_admin_role():
    user = client.post("/signup", json={"email": "plainuser@example.com", "password": "pw123456"}).json()
    # a normal USER is forbidden
    r = client.get("/admin/users", headers=_auth(user["access_token"]))
    assert r.status_code == 403


def test_admin_can_list_and_promote():
    create_admin("admin@example.com", "adminpass")
    admin = client.post("/login", json={"email": "admin@example.com", "password": "adminpass"}).json()

    target = client.post("/signup", json={"email": "promote@example.com", "password": "pw123456"}).json()
    me = client.get("/me", headers=_auth(target["access_token"])).json()

    listing = client.get("/admin/users", headers=_auth(admin["access_token"]))
    assert listing.status_code == 200
    assert any(u["email"] == "promote@example.com" for u in listing.json())

    promoted = client.post(f"/admin/users/{me['id']}/role",
                           json={"role": "ADMIN"}, headers=_auth(admin["access_token"]))
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "ADMIN"


def test_disabled_user_cannot_login():
    create_admin("admin2@example.com", "adminpass")
    admin = client.post("/login", json={"email": "admin2@example.com", "password": "adminpass"}).json()
    victim = client.post("/signup", json={"email": "victim@example.com", "password": "pw123456"}).json()
    vid = client.get("/me", headers=_auth(victim["access_token"])).json()["id"]

    client.post(f"/admin/users/{vid}/disable", headers=_auth(admin["access_token"]))
    r = client.post("/login", json={"email": "victim@example.com", "password": "pw123456"})
    assert r.status_code == 403
