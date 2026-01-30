"""
Script to create test users in the database.
Run this from the backend root directory:
    python scripts/create_test_users.py
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine
from app.models.user import User
from app.core.security import get_password_hash


def create_test_users():
    """Create test users for development"""
    db = SessionLocal()
    
    test_users = [
        {
            "email": "yellow8012@gmail.com",
            "full_name": "Test User Yellow",
            "password": "Password123",
            "is_active": True,
            "is_verified": True,
            "is_superuser": True
        },
        {
            "email": "kao264918@gmail.com",
            "full_name": "Test User Kao",
            "password": "Password123",
            "is_active": True,
            "is_verified": True,
            "is_superuser": True
        }
    ]
    
    try:
        for user_data in test_users:
            # Check if user already exists
            existing = db.query(User).filter(User.email == user_data["email"]).first()
            if existing:
                print(f"User {user_data['email']} already exists, updating password...")
                existing.hashed_password = get_password_hash(user_data["password"])
                existing.is_active = True
                existing.is_verified = True
            else:
                print(f"Creating user {user_data['email']}...")
                new_user = User(
                    email=user_data["email"],
                    full_name=user_data["full_name"],
                    hashed_password=get_password_hash(user_data["password"]),
                    is_active=user_data["is_active"],
                    is_verified=user_data["is_verified"],
                    is_superuser=user_data["is_superuser"]
                )
                db.add(new_user)
        
        db.commit()
        print("\n✅ Test users created/updated successfully!")
        print("   - yellow8012@gmail.com / Password123")
        print("   - kao264918@gmail.com / Password123")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_test_users()
