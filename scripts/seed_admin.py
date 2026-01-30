import logging
import sys
from sqlalchemy.orm import Session

# Add the parent directory to sys.path to resolve imports
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine, Base
from app import models
from app.core.security import get_password_hash

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_admin(db: Session, email: str, password: str, full_name: str) -> None:
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        user = models.User(
            email=email,
            hashed_password=get_password_hash(password),
            full_name=full_name,
            is_active=True,
            is_superuser=True,
            is_verified=True,
            job_title="System Administrator",
            company_name="Ventto Design"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Created Admin User: {email}")
    else:
        # Update password just in case
        user.hashed_password = get_password_hash(password)
        user.is_verified = True
        db.commit()
        logger.info(f"Admin User already exists (Updated password/status): {email}")

def main() -> None:
    logger.info("Initializing Database...")
    try:
        # Create all tables (ensure User table exists)
        Base.metadata.create_all(bind=engine)
        logger.info("Tables created (if not existed).")

        db = SessionLocal()
        
        # Admin Seed Data
        seed_admin(db, "admin@ventto.design", "admin", "Admin User")
        # seed_admin(db, "pm@ventto.design", "admin", "Product Manager")

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    main()
