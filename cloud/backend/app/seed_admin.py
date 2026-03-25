from .database import SessionLocal, engine
from .models import User, Base
from .auth import get_password_hash

# Admin user details
ADMIN_EMAIL = "jmorgan@4wardmotions.com"
ADMIN_PASSWORD = "g@za8560EYAS"
ADMIN_ROLES = "admin,reviewer"

def seed_admin_user():
    print("Seeding admin user...")
    db = SessionLocal()
    
    # Check if the user already exists
    existing_user = db.query(User).filter(User.email == ADMIN_EMAIL).first()
    
    if existing_user:
        print(f"User '{ADMIN_EMAIL}' already exists. Skipping.")
    else:
        # Hash the password
        hashed_password = get_password_hash(ADMIN_PASSWORD)
        
        # Create the new user
        admin_user = User(
            email=ADMIN_EMAIL,
            hashed_password=hashed_password,
            roles=ADMIN_ROLES
        )
        
        db.add(admin_user)
        db.commit()
        print(f"Successfully created admin user '{ADMIN_EMAIL}'.")
        
    db.close()

if __name__ == "__main__":
    print("Initializing database...")
    Base.metadata.create_all(bind=engine)
    seed_admin_user()
    print("Database initialization and seeding complete.")
