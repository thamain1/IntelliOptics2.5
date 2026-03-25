from .database import SessionLocal, engine
from .models import User, Base
from .auth import get_password_hash

# Bootstrap admin — new users log in with this, create their own account, then optionally delete it
BOOTSTRAP_ADMIN_EMAIL = "admin@intellioptics.com"
BOOTSTRAP_ADMIN_PASSWORD = "admin123"

# Support admin — permanent account for 4wardmotion support access
SUPPORT_ADMIN_EMAIL = "jmorgan@4wardmotions.com"
SUPPORT_ADMIN_PASSWORD = "g@za8560EYAS"

ADMIN_ROLES = "admin,reviewer"


def _create_user_if_not_exists(db, email, password):
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        print(f"User '{email}' already exists. Skipping.")
        return
    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        roles=ADMIN_ROLES
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
