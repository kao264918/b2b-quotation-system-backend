from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.user import User
from app.schemas.auth import LoginRequest
from app.core.security import verify_password as bcrypt_verify, get_password_hash as bcrypt_hash
from uuid import UUID

class CRUDUser:
    def get_by_email(self, db: Session, email: str) -> User | None:
        return db.scalar(select(User).where(User.email == email))

    def get(self, db: Session, id: UUID) -> User | None:
        return db.scalar(select(User).where(User.id == id))

    def authenticate(self, db: Session, email: str, password: str) -> User | None:
        user = self.get_by_email(db, email)
        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        return user

    def create(self, db: Session, email: str, password: str, full_name: str = None, is_superuser: bool = False, is_active: bool = True) -> User:
        db_user = User(
            email=email,
            hashed_password=self.get_password_hash(password),
            full_name=full_name,
            is_superuser=is_superuser,
            is_active=is_active
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        try:
            return bcrypt_verify(plain_password, hashed_password)
        except Exception:
            return False

    def get_password_hash(self, password: str) -> str:
        return bcrypt_hash(password)

user = CRUDUser()
