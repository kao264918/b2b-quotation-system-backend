from __future__ import annotations

import os
import sys
import uuid

from fastapi.testclient import TestClient
import pytest

# Ensure backend root is importable when pytest is executed from CI/local with varying PYTHONPATH.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.crud.user import user as crud_user
from app.database import SessionLocal
from app.main import app
from app.models.session import RefreshSession
from app.models.user import User


@pytest.fixture()
def test_user_credentials():
    db = SessionLocal()
    email = f"cors-smoke-{uuid.uuid4().hex[:12]}@example.com"
    password = "CorsSmoke123!"

    db_user = User(
        email=email,
        hashed_password=crud_user.get_password_hash(password),
        full_name="CORS Smoke User",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    try:
        yield {"email": email, "password": password, "user_id": str(db_user.id)}
    finally:
        db.query(RefreshSession).filter(RefreshSession.user_id == db_user.id).delete()
        db.query(User).filter(User.id == db_user.id).delete()
        db.commit()
        db.close()


def test_cors_and_auth_smoke(test_user_credentials):
    client = TestClient(app)

    allowed_origin = "http://localhost:5173"
    preview_origin = "https://feat-123-b2b-quotation-system.vercel.app"
    blocked_origin = "https://evil.example.com"

    # 1) CSRF token endpoint should be reachable.
    csrf_response = client.get("/api/v1/auth/csrf", headers={"Origin": allowed_origin})
    assert csrf_response.status_code == 200
    csrf_token = csrf_response.json()["csrf_token"]
    assert csrf_token

    # 2) Login should set session cookie.
    login_response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": allowed_origin},
        json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"],
            "remember_me": False,
        },
    )
    assert login_response.status_code == 200
    assert "session_id" in login_response.headers.get("set-cookie", "")

    # 3) Authenticated /me must return 200.
    me_response = client.get("/api/v1/auth/me", headers={"Origin": allowed_origin})
    assert me_response.status_code == 200
    assert me_response.json()["email"] == test_user_credentials["email"]

    # 4) A protected business endpoint should be reachable after login.
    protected_response = client.get("/api/v1/customers", headers={"Origin": allowed_origin})
    assert protected_response.status_code == 200

    # 5) Unsafe request without CSRF header must be rejected.
    missing_csrf_response = client.post(
        "/api/v1/customers",
        headers={"Origin": allowed_origin},
        json={},
    )
    assert missing_csrf_response.status_code == 403
    assert missing_csrf_response.json()["detail"] == "CSRF token missing or invalid"

    # 6) Unsafe request from disallowed origin must be rejected.
    blocked_origin_response = client.post(
        "/api/v1/customers",
        headers={"Origin": blocked_origin, "X-CSRF-Token": csrf_token},
        json={},
    )
    assert blocked_origin_response.status_code == 403
    assert blocked_origin_response.json()["detail"] == "Origin not allowed"

    # 7) Preview origin preflight should be accepted when matching regex.
    preview_preflight = client.options(
        "/api/v1/customers",
        headers={
            "Origin": preview_origin,
            "Access-Control-Request-Method": "POST",
        },
    )
    assert preview_preflight.status_code in (200, 204)
    assert preview_preflight.headers.get("access-control-allow-origin") == preview_origin
