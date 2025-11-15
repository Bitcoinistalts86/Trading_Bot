# auth_service/tests/test_auth.py
import pytest
from unittest.mock import patch
from jose import jwt
from passlib.context import CryptContext

from ..app.main import create_access_token, SECRET_KEY, ALGORITHM

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def test_password_hashing():
    password = "testpassword"
    hashed_password = pwd_context.hash(password)
    assert pwd_context.verify(password, hashed_password)
    assert not pwd_context.verify("wrongpassword", hashed_password)

@patch('auth_service.app.main.SECRET_KEY', "test-secret")
def test_jwt_signing_and_verification():
    data = {"sub": "testuser", "role": "USER"}
    token = create_access_token(data)
    decoded_payload = jwt.decode(token, "test-secret", algorithms=[ALGORITHM])
    assert decoded_payload["sub"] == "testuser"
    assert decoded_payload["role"] == "USER"
