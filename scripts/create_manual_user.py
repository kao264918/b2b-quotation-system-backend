import sys
import os
from datetime import datetime, timezone

# Add parent dir to path
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app.crud import user as crud_user
from app.models.user import User

def create_manual_user(email, password):
    db = SessionLocal()
    try:
        # Check if exists
        existing = crud_user.user.get_by_email(db, email=email)
        if existing:
            print(f"User {email} already exists. Updating password...")
            existing.hashed_password = crud_user.user.get_password_hash(password)
            existing.is_active = True
            existing.is_verified = True
            existing.email_verified_at = datetime.now(timezone.utc)
            db.add(existing)
            db.commit()
            print(f"✅ User {email} updated. Password: {password}")
            return

        # Create new
        print(f"Creating user {email}...")
        user = User(
            email=email,
            hashed_password=crud_user.user.get_password_hash(password),
            full_name="Test User",
            is_active=True,
            is_superuser=False,
            is_verified=True,
            email_verified_at=datetime.now(timezone.utc)
        )
        db.add(user)
        db.commit()
        print(f"✅ User {email} created successfully. Password: {password}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    import getpass
    
    print("--- Create Manual User ---")
    email = input("Enter Email: ").strip()
    if not email:
        print("Error: Email is required.")
        sys.exit(1)
    
    # Secure password input
    password = getpass.getpass("Enter Password: ").strip()
    if not password:
        print("Error: Password is required.")
        sys.exit(1)
        
    create_manual_user(email, password)
