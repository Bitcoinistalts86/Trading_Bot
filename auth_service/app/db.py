# auth_service/app/db.py
"""
Database layer for the auth service.

Replaces the previous design that used BigQuery as a user store -- BigQuery is an
analytics warehouse (high per-row latency, no unique constraints, eventual
consistency on streaming inserts), which made the duplicate-email check racy.
This uses a real relational database via SQLAlchemy.

Default: SQLite file (zero-config, works locally, in Docker, and in tests).
Production: set DATABASE_URL to a Postgres DSN -- nothing else changes.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./auth.db")

# SQLite needs check_same_thread=False to be used across FastAPI's threadpool.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def init_db() -> None:
    """Create tables. Idempotent. For real migrations, use Alembic."""
    from . import models  # noqa: F401 -- ensure models are registered
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency that yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
