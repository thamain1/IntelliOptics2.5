"""Authentication utilities for the IntelliOptics backend.

This module implements a standard OAuth2 password-based authentication
flow using JWTs. It also includes utilities for password hashing.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

from jose import JWTError, jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from . import models, schemas
from .config import get_settings
from .database import SessionLocal, get_db


# --- Password Hashing Setup ---
# Switched to pbkdf2_sha256 due to bcrypt 4.0+ compatibility issues with passlib 1.7.4
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- Router for authentication ---
router = APIRouter(tags=["authentication"])

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain-text password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hashes a plain-text password."""
    return pwd_context.hash(password)

def authenticate_user(db: Session, email: str, password: str) -> Optional[models.User]:
    """Authenticates a user by email and password."""
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not user.hashed_password:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JWT access token."""
    to_encode = data.copy()
    settings = get_settings()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.api_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt

def create_fallback_token(detector_id: str) -> str:
    """Creates a short-lived token for fallback operations."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.fallback_token_expiry_minutes)
    to_encode = {
        "sub": f"fallback:{detector_id}",
        "type": "fallback",
        "exp": expire
    }
    encoded_jwt = jwt.encode(to_encode, settings.api_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt

@router.post("/token", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    user = authenticate_user(db, email=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=get_settings().access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.email, "roles": user.roles.split(',') if user.roles else []}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    """
    FastAPI dependency to authenticate a request via JWT and return the current user.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        settings = get_settings()
        payload = jwt.decode(token, settings.api_secret_key, algorithms=[settings.jwt_algorithm])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

def require_role(role: str):
    """
    Return a dependency that ensures the current user has the given role.
    """
    async def _checker(user: models.User = Depends(get_current_user)) -> models.User:
        user_roles = user.roles.split(',') if user.roles else []
        if role not in user_roles:
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return user
    return _checker
