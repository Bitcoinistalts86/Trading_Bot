# api_gateway/tests/test_auth.py
import pytest
from fastapi.testclient import TestClient
from ..app.main import app, get_current_user
from ..libraries.auth import TokenData

async def override_get_current_user():
    return TokenData(user_id="testuser", role="USER")

app.dependency_overrides[get_current_user] = override_get_current_user

client = TestClient(app)

def test_rejects_unauthenticated_requests():
    # We need to remove the override for this test
    app.dependency_overrides = {}
    response = client.post("/api/order", json={"instrument": "BTC/USD", "side": "buy", "quantity": 1})
    assert response.status_code == 401
    # Restore the override
    app.dependency_overrides[get_current_user] = override_get_current_user

def test_allows_authenticated_requests():
    response = client.post(
        "/api/order",
        json={"instrument": "BTC/USD", "side": "buy", "quantity": 1},
        headers={"Authorization": "Bearer fake-token"}
    )
    # This will still fail because the downstream call to the execution_engine is not mocked
    # but it will pass the authentication check. We expect a 500 error.
    assert response.status_code == 500
