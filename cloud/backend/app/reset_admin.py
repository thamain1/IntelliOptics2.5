"""FORCIBLY reset the admin user — deletes existing row and recreates.

This script is DESTRUCTIVE. Any UI-side password change will be overwritten.
It exists for emergency lockout recovery. In normal operation, prefer
create_admin.py (upsert) or leave the already-seeded admin alone.

Credentials read from environment variables (fall back to documented defaults
if unset):

    ADMIN_EMAIL       default: jmorgan@4wardmotions.com
    ADMIN_PASSWORD    default: g@za8560EYAS
    ADMIN_ROLES       default: "admin,reviewer"

Run:
    docker exec intellioptics-cloud-backend python -m app.reset_admin
"""
import os

from .database import SessionLocal, engine
from .models import User, Base
from .auth import get_password_hash

ADMIN_EMAIL    = os.environ.get("ADMIN_EMAIL",    "jmorgan@4wardmotions.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "g@za8560EYAS")
ADMIN_ROLES    = os.environ.get("ADMIN_ROLES",    "admin,reviewer")


def reset_admin_user():
    print(f"Resetting admin user '{ADMIN_EMAIL}'...")
    db = SessionLocal()

    # 1. Delete existing user if found
    existing_user = db.query(User).filter(User.email == ADMIN_EMAIL).first()
    if existing_user:
        print(f"Found existing user. Deleting ID: {existing_user.id}")
        db.delete(existing_user)
        db.commit()
    else:
        print("No existing user found.")

    # 2. Create new user with fresh hash
    print("Hashing password...")
    hashed_password = get_password_hash(ADMIN_PASSWORD)

    new_admin_user = User(
        email=ADMIN_EMAIL,
        hashed_password=hashed_password,
        roles=ADMIN_ROLES,
    )

    print("Creating new user record...")
    db.add(new_admin_user)
    db.commit()
    print(f"Successfully reset admin user '{ADMIN_EMAIL}'.")

    db.close()


if __name__ == "__main__":
    reset_admin_user()
