from app.database import engine, Base
from sqlalchemy import text
from app.models.user import User
from app.models.session import RefreshSession
from app.models.token import VerificationToken, PasswordResetToken

def reset_db():
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS verification_tokens CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS password_reset_tokens CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS refresh_sessions CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS users CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
        conn.commit()
    print("Auth tables dropped.")

if __name__ == "__main__":
    reset_db()
