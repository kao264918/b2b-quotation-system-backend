from __future__ import annotations

import os
import sys

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal


@pytest.fixture(scope="session")
def ensure_database_available():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    except OperationalError as exc:
        pytest.skip(f"Database unavailable for integration tests: {exc}")
    finally:
        db.close()

