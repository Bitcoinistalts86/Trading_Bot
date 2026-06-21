# auth_service/app/schemas.py
"""Pydantic request/response models for the auth API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class RoleUpdate(BaseModel):
    role: str  # USER | ADMIN


class UserOut(BaseModel):
    id: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None

    class Config:
        from_attributes = True
