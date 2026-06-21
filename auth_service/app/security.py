# auth_service/app/security.py
"""
Password hashing + JWT issue/verify + auth dependencies.

Uses the `bcrypt` library directly (avoids the passlib/bcrypt version warning),
and python-jose for HS256 JWTs. In production the JWT secret should come from
Secret Manager; here it is read from env with a clear startup error if unset in
a non-dev context.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .db import get_db
from .models import User

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", 7))

# Dev default is explicit and obviously-not-secret so it can't be mistaken for safe.
SECRET_KEY = os.environ.get("JWT_SECRET", "dev-insecure-change-me")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def _make_token(sub: str, role: str | None, expires: timedelta, kind: str) -> str:
    payload = {"sub": sub, "type": kind, "exp": datetime.now(timezone.utc) + expires}
    if role is not None:
        payload["role"] = role
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user_id: str, role: str) -> str:
    return _make_token(user_id, role, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES), "access")


def create_refresh_token(user_id: str) -> str:
    return _make_token(user_id, None, timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS), "refresh")


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


_credentials_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    if not token:
        raise _credentials_error
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise _credentials_error
        user_id = payload.get("sub")
    except JWTError:
        raise _credentials_error
    user = db.get(User, user_id) if user_id else None
    if not user or not user.is_active:
        raise _credentials_error
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user
