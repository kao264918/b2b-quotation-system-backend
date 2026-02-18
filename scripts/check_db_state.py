import sys
import os
from sqlalchemy import create_engine, inspect, text

# Add parent directory
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings

def check_db():
    print(f"Connecting to: {settings.DATABASE_URL}")
    engine = create_engine(settings.DATABASE_URL)
    inspector = inspect(engine)
    columns = inspector.get_columns("users")
    print("Columns in 'users' table:")
    for col in columns:
        print(f" - {col['name']} ({col['type']})")
        
    # Check alembic_version
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version_num FROM alembic_version"))
        version = result.scalar()
        print(f"Current Alembic Version in DB: {version}")

if __name__ == "__main__":
    check_db()
