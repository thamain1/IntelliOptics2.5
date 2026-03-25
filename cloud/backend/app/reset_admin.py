from .database import SessionLocal, engine
from .models import User, Base
from .auth import get_password_hash

# Admin user details
ADMIN_EMAIL = "jmorgan@4wardmotions.com"
ADMIN_PASSWORD = "g@za8560EYAS"
ADMIN_ROLES = "admin,reviewer"

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
        roles=ADMIN_ROLES
    )
    
    print("Creating new user record...")
    db.add(new_admin_user)
    db.commit()
    print(f"Successfully reset admin user '{ADMIN_EMAIL}'.")
        
    db.close()

if __name__ == "__main__":
    reset_admin_user()
