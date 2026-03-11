import sys
import os
from urllib.parse import urlparse
from sqlalchemy import create_engine, inspect, text

# Add parent directory
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings


def mask_database_url(database_url: str) -> str:
    parsed = urlparse(database_url)
    host = parsed.hostname or "unknown-host"
    port = parsed.port or "default"
    database = parsed.path.lstrip("/") or "unknown-db"
    scheme = parsed.scheme or "unknown-driver"
    return f"{scheme}://***:***@{host}:{port}/{database}"

def check_db():
    print(f"Connecting to: {mask_database_url(settings.DATABASE_URL)}")
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
