# auth_service/tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from ..app.main import app

@pytest.fixture
def client():
    with patch('auth_service.app.main.bq_client', new_callable=MagicMock) as mock_bq_client, \
         patch('auth_service.app.main.secret_client', new_callable=MagicMock) as mock_secret_client:

        # Mock the secret client to return a fake secret
        mock_secret_payload = MagicMock()
        mock_secret_payload.data = b"test-secret"
        mock_access_response = MagicMock()
        mock_access_response.payload = mock_secret_payload
        mock_secret_client.access_secret_version.return_value = mock_access_response

        yield TestClient(app)

def test_signup(client):
    # Mock the BigQuery client to simulate no existing user
    mock_query_job = MagicMock()
    mock_query_job.result.return_value.total_rows = 0
    client.app.bq_client.query.return_value = mock_query_job

    # Mock the insert operation
    client.app.bq_client.insert_rows_json.return_value = []

    response = client.post("/signup", json={"email": "test@example.com", "password": "password"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data

def test_login(client):
    # Mock the BigQuery client to simulate an existing user
    mock_user_row = MagicMock()
    mock_user_row.user_id = "testuser"
    mock_user_row.role = "USER"
    mock_user_row.password_hash = "$2b$12$E8.Oul.20a3.b7.a.e.f.Oul.20a3.b7.a.e.f.Oul.2" # Fake hash
    mock_query_job = MagicMock()
    mock_query_job.result.return_value = [mock_user_row]
    client.app.bq_client.query.return_value = mock_query_job

    # Mock password verification
    with patch('auth_service.app.main.pwd_context.verify', return_value=True):
        response = client.post("/login", json={"email": "test@example.com", "password": "password"})
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
