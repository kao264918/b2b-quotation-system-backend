import logging
import os
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.crud import user as crud_user
from app.models.user import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_users(db: Session) -> None:
    # Safety Check: Do not run in production unless forced
    env = os.getenv("ENVIRONMENT", "development")
    force_seed = os.getenv("SEED_USERS", "false").lower() == "true"
    
    if env == "production" and not force_seed:
        logger.warning("Skipping seed_users in production. Set SEED_USERS=true to force.")
        return

    # Ensure tables exist (Dev only or if forced)
    from app.database import engine
    from app.models import User
    from app.database import Base
    Base.metadata.create_all(bind=engine)
    
    # 1. Dev Admin

    # 1. Dev Admin
    email = os.getenv("DEV_ADMIN_EMAIL", "admin@example.com")
    password = os.getenv("DEV_ADMIN_PASSWORD", "password123")
    
    user = crud_user.user.get_by_email(db, email=email)
    if not user:
        user = crud_user.user.create(
            db=db,
            email=email,
            password=password,
            full_name="Dev Admin",
            is_superuser=True,
            is_active=True
        )
        logger.info(f"Created Admin User: {email}")
    else:
        logger.info(f"Admin User {email} already exists")

def main() -> None:
    logger.info("Seeding users...")
    db = SessionLocal()
    try:
        seed_users(db)
    except Exception as e:
        logger.error(f"Error seeding users: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
