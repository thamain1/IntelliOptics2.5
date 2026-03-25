"""Create or reset the admin user."""
import sys
sys.path.insert(0, '/app')

from app.database import SessionLocal, engine
from app.models import User, Base
from app.auth import get_password_hash

ADMIN_EMAIL = "jmorgan@4wardmotions.com"
ADMIN_PASSWORD = "g@za8560EYAS"
ADMIN_ROLES = "admin,reviewer"

def main():
    print("=" * 50)
    print("CREATE/RESET ADMIN USER")
    print("=" * 50)

    # Ensure tables exist
    print("\n1. Creating database tables if needed...")
    try:
        Base.metadata.create_all(bind=engine)
        print("   SUCCESS: Tables ready")
    except Exception as e:
        print(f"   FAILED: {e}")
        return

    # Create or update admin user
    print(f"\n2. Setting up admin user: {ADMIN_EMAIL}")
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == ADMIN_EMAIL).first()

        hashed = get_password_hash(ADMIN_PASSWORD)

        if existing:
            print("   User exists, updating password...")
            existing.hashed_password = hashed
            existing.roles = ADMIN_ROLES
        else:
            print("   Creating new user...")
            user = User(
                email=ADMIN_EMAIL,
                hashed_password=hashed,
                roles=ADMIN_ROLES
            )
            db.add(user)

        db.commit()
        print("   SUCCESS: Admin user ready!")
        print(f"\n   Email: {ADMIN_EMAIL}")
        print(f"   Password: {ADMIN_PASSWORD}")
        print(f"   Roles: {ADMIN_ROLES}")

    except Exception as e:
        print(f"   FAILED: {e}")
        db.rollback()
    finally:
        db.close()

    print("\n" + "=" * 50)
    print("COMPLETE - You can now log in")
    print("=" * 50)

if __name__ == "__main__":
    main()
