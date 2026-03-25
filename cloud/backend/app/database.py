"""Database session and base class setup.

This module configures SQLAlchemy for use throughout the backend.  It
creates an engine from the provided DSN, defines a session factory
using `sessionmaker`, and exposes the declarative base used by the
model definitions.
"""
from __future__ import annotations

from typing import Generator # Add import

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import get_settings


settings = get_settings()

# Create a SQLAlchemy engine.  The `future=True` flag opts into SQL
# Alchemy 2.0 style behaviour.
engine = create_engine(settings.database.dsn, pool_pre_ping=True, future=True)

# Session factory configured with autocommit disabled and autflush
# disabled.  A scoped session could also be used, but explicit
# dependency injection via FastAPI is preferred.
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)

# Declarative base class for ORM models.
Base = declarative_base()


def get_db() -> Generator:
    """Dependency that yields a SQLAlchemy session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
