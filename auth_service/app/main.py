# auth_service/app/main.py
"""
Authentication & user-management service (SQL-backed).

Endpoints:
  GET  /health
  POST /signup            -> create USER, return tokens
  POST /login             -> verify credentials, return tokens
  POST /refresh           -> exchange a refresh token for new tokens
  GET  /me                -> current user's profile  (auth)
  GET  /admin/users       -> list users              (admin)
  POST /admin/users/{id}/role     -> change role     (admin)
  POST /admin/users/{id}/disable  -> deactivate user (admin)
  POST /admin/users/{id}/enable   -> reactivate user (admin)

Roles: USER (default) and ADMIN. JWTs carry `sub` (user id) and `role`.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError
from sqlalchemy.orm import Session

from .db import get_db, init_db
from .models import User
from .schemas import RefreshRequest, RoleUpdate, Token, UserCreate, UserLogin, UserOut
from .security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    require_admin,
    verify_password,
)

logger = logging.getLogger("auth_service")
app = FastAPI(title="Authentication Service")

# CORS so the dashboard (different origin in dev) can call this service.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_VALID_ROLES = {"USER", "ADMIN"}


def _tokens(user: User) -> Token:
    return Token(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id),
    )


@app.on_event("startup")
def _startup() -> None:
    init_db()
    _maybe_bootstrap_admin()


def _maybe_bootstrap_admin() -> None:
    """Optionally create an admin from env on first boot (handy for compose)."""
    email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL")
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD")
    if not (email and password):
        return
    from .db import SessionLocal
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == email).first():
            db.add(User(email=email, password_hash=hash_password(password), role="ADMIN"))
            db.commit()
            logger.warning("Bootstrapped admin user %s", email)
    finally:
        db.close()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/signup", response_model=Token)
def signup(payload: UserCreate, db: Session = Depends(get_db)) -> Token:
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=payload.email, password_hash=hash_password(payload.password), role="USER")
    db.add(user)
    db.commit()
    db.refresh(user)
    return _tokens(user)


@app.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> Token:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return _tokens(user)


@app.post("/refresh", response_model=Token)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> Token:
    err = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    try:
        claims = decode_token(payload.refresh_token)
        if claims.get("type") != "refresh":
            raise err
        user_id = claims.get("sub")
    except JWTError:
        raise err
    user = db.get(User, user_id) if user_id else None
    if not user or not user.is_active:
        raise err
    return _tokens(user)


@app.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


# --- admin ----------------------------------------------------------------- #
@app.get("/admin/users", response_model=list[UserOut])
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[User]:
    return db.query(User).order_by(User.created_at.desc()).all()


@app.post("/admin/users/{user_id}/role", response_model=UserOut)
def set_role(user_id: str, body: RoleUpdate, admin: User = Depends(require_admin),
             db: Session = Depends(get_db)) -> User:
    role = body.role.upper()
    if role not in _VALID_ROLES:
        raise HTTPException(status_code=400, detail="role must be USER or ADMIN")
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.role = role
    db.commit()
    db.refresh(target)
    return target


@app.post("/admin/users/{user_id}/disable", response_model=UserOut)
def disable_user(user_id: str, admin: User = Depends(require_admin),
                 db: Session = Depends(get_db)) -> User:
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Admins cannot disable themselves")
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.is_active = False
    db.commit()
    db.refresh(target)
    return target


@app.post("/admin/users/{user_id}/enable", response_model=UserOut)
def enable_user(user_id: str, _: User = Depends(require_admin),
                db: Session = Depends(get_db)) -> User:
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.is_active = True
    db.commit()
    db.refresh(target)
    return target
