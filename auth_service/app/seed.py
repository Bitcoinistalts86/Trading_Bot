# auth_service/app/seed.py
"""CLI to create an admin user. Usage:  python -m app.seed --email a@b.com --password ..."""
from __future__ import annotations

import argparse

from .db import SessionLocal, init_db
from .models import User
from .security import hash_password


def create_admin(email: str, password: str) -> str:
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            existing.role = "ADMIN"
            existing.is_active = True
            db.commit()
            return f"Promoted existing user {email} to ADMIN"
        db.add(User(email=email, password_hash=hash_password(password), role="ADMIN"))
        db.commit()
        return f"Created ADMIN user {email}"
    finally:
        db.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    args = p.parse_args()
    print(create_admin(args.email, args.password))
