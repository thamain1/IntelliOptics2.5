"""Seed the admin + bootstrap users.

Idempotent — creates users only if they do not already exist. Safe to run on
every container start.

Credentials read from environment variables (fall back to documented defaults
if unset, so legacy deploy scripts keep working):

    ADMIN_EMAIL             e.g. jmorgan@4wardmotions.com
    ADMIN_PASSWORD          the password the admin will log in with
    ADMIN_ROLES             comma-separated roles, default "admin,reviewer"
    BOOTSTRAP_ADMIN_EMAIL   first-login helper account, default admin@intellioptics.com
    BOOTSTRAP_ADMIN_PASSWORD  default "admin123" — CHANGE IN PRODUCTION

If you want to change your permanent admin password, set ADMIN_PASSWORD in
the backend container's .env file and run ONE of:
    - docker compose restart backend        (no password change for existing user)
    - docker exec intellioptics-cloud-backend python -m app.create_admin   (force reset)
"""
import os

from .database import SessionLocal, engine
from .models import User, Base
from .auth import get_password_hash

# ---------------------------------------------------------------------------
# Env-driven defaults (fall back to historical hardcodes so nothing breaks)
# ---------------------------------------------------------------------------

BOOTSTRAP_ADMIN_EMAIL    = os.environ.get("BOOTSTRAP_ADMIN_EMAIL",    "admin@intellioptics.com")
BOOTSTRAP_ADMIN_PASSWORD = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "admin123")

SUPPORT_ADMIN_EMAIL      = os.environ.get("ADMIN_EMAIL",    "jmorgan@4wardmotions.com")
SUPPORT_ADMIN_PASSWORD   = os.environ.get("ADMIN_PASSWORD", "g@za8560EYAS")

ADMIN_ROLES = os.environ.get("ADMIN_ROLES", "admin,reviewer")


def _create_user_if_not_exists(db, email, password):
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        print(f"User '{email}' already exists. Skipping.")
        return
    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        roles=ADMIN_ROLES,
    )
    db.add(user)
    db.commit()
    print(f"Successfully created admin user '{email}'.")


def seed_admin_user():
    print("Seeding admin users...")
    db = SessionLocal()
    _create_user_if_not_exists(db, BOOTSTRAP_ADMIN_EMAIL, BOOTSTRAP_ADMIN_PASSWORD)
    _create_user_if_not_exists(db, SUPPORT_ADMIN_EMAIL, SUPPORT_ADMIN_PASSWORD)
    db.close()


if __name__ == "__main__":
    print("Initializing database...")
    Base.metadata.create_all(bind=engine)
    seed_admin_user()
    print("Database initialization and seeding complete.")
