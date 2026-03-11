#!/usr/bin/env python3
"""
創建用戶腳本 - 支援任意資料庫

使用方式：
1. 本機 (使用 .env 的 DATABASE_URL):
   python scripts/create_user_any_db.py

2. Production (指定 DATABASE_URL):
   DATABASE_URL="postgresql://..." python scripts/create_user_any_db.py

3. 自訂帳密:
   EMAIL="user@example.com" PASSWORD="MyPass123" python scripts/create_user_any_db.py

4. Railway (透過 Railway CLI):
   railway run python scripts/create_user_any_db.py
"""
import sys
import os
from datetime import datetime, timezone
from urllib.parse import urlparse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add parent dir to path
sys.path.append(os.getcwd())

from app.crud import user as crud_user
from app.models.user import User


def mask_database_target(db_url: str) -> str:
    parsed = urlparse(db_url)
    host = parsed.hostname or "unknown-host"
    port = parsed.port or "default"
    database = parsed.path.lstrip("/") or "unknown-db"
    return f"{host}:{port}/{database}"

def create_manual_user(db_url: str, email: str, password: str, full_name: str = "Manual User"):
    """
    Create or update a user in the specified database
    
    Args:
        db_url: PostgreSQL connection string
        email: User email
        password: Plain text password (will be hashed)
        full_name: User's full name
    """
    # Create engine and session
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Check if exists
        existing = crud_user.user.get_by_email(db, email=email)
        if existing:
            print(f"⚠️  User {email} already exists. Updating password...")
            existing.hashed_password = crud_user.user.get_password_hash(password)
            existing.is_active = True
            existing.is_verified = True
            existing.email_verified_at = datetime.now(timezone.utc)
            existing.full_name = full_name
            db.add(existing)
            db.commit()
            print(f"✅ User {email} updated successfully!")
            return

        # Create new
        print(f"🔨 Creating new user {email}...")
        user = User(
            email=email,
            hashed_password=crud_user.user.get_password_hash(password),
            full_name=full_name,
            is_active=True,
            is_superuser=False,
            is_verified=True,
            email_verified_at=datetime.now(timezone.utc)
        )
        db.add(user)
        db.commit()
        print(f"✅ User {email} created successfully!")
        print(f"   Email: {email}")
        print(f"   Full Name: {full_name}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    # Get DATABASE_URL from env or .env file
    from dotenv import load_dotenv
    load_dotenv()
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ Error: DATABASE_URL not found in environment")
        print("   Set it via: DATABASE_URL='postgresql://...' python scripts/create_user_any_db.py")
        sys.exit(1)
    
    email = os.getenv("EMAIL")
    password = os.getenv("PASSWORD")
    full_name = os.getenv("FULL_NAME", "Example User")

    if not email:
        print("❌ Error: EMAIL environment variable is required")
        sys.exit(1)

    if not password:
        print("❌ Error: PASSWORD environment variable is required")
        sys.exit(1)

    print(f"📊 Database: {mask_database_target(db_url)}")
    print(f"📧 Email: {email}")
    print(f"🔐 Password: {'*' * len(password)}")
    print()
    
    create_manual_user(db_url, email, password, full_name)
