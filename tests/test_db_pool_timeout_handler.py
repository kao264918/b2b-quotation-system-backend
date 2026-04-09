from fastapi.testclient import TestClient
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

from app.deps.auth import get_current_user
from app.main import app


def test_db_pool_timeout_returns_503_without_traceback_bubble():
    def override_current_user():
        raise SQLAlchemyTimeoutError("QueuePool exhausted")

    app.dependency_overrides[get_current_user] = override_current_user

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/catalog-items")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert response.json() == {
        "detail": "Database is busy. Please retry shortly.",
        "code": "DB_POOL_TIMEOUT",
    }
