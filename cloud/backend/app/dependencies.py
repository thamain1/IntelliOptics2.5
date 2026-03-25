"""Common FastAPI dependencies used throughout the backend."""
from __future__ import annotations

from typing import Generator

from fastapi import Depends

from . import models
from .database import SessionLocal, get_db
from .auth import get_current_user, require_role


def get_current_admin(user: models.User = Depends(get_current_user)) -> models.User:
    """Dependency to ensure the user has the admin role."""
    # Simple role check assuming roles is a comma-separated string
    user_roles = user.roles.split(',') if user.roles else []
    if "admin" not in user_roles:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Not enough permissions")
    return user


def get_current_reviewer(user: models.User = Depends(get_current_user)) -> models.User:
    """Dependency to ensure the user has the reviewer role."""
    user_roles = user.roles.split(',') if user.roles else []
    if "reviewer" not in user_roles and "admin" not in user_roles:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Not enough permissions")
    return user
