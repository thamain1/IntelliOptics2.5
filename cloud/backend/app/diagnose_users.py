"""Diagnostic script to check user database status."""
import sys
sys.path.insert(0, '/app')

from app.database import SessionLocal, engine
from app.models import User

def main():
    print("=" * 50)
    print("USER DATABASE DIAGNOSTIC")
    print("=" * 50)

    # Test DB connection
    print("\n1. Testing database connection...")
    try:
        conn = engine.connect()
        print(f"   SUCCESS: Connected to {engine.url}")
        conn.close()
    except Exception as e:
        print(f"   FAILED: {e}")
        return

    # List all users
    print("\n2. Listing all users...")
    db = SessionLocal()
    try:
        users = db.query(User).all()
        print(f"   Total users in database: {len(users)}")

        if users:
            for u in users:
                has_pw = "YES" if u.hashed_password else "NO"
                print(f"   - {u.email} | roles: {u.roles} | has_password: {has_pw}")
        else:
            print("   WARNING: No users found! Run: python -m app.create_admin")
    except Exception as e:
        print(f"   ERROR: {e}")
    finally:
        db.close()

    print("\n" + "=" * 50)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 50)

if __name__ == "__main__":
    main()
