"""
Smoke tests for core business endpoints: item, rfq, customer, quote.
These tests verify that the core endpoints remain healthy and are
not broken by onboarding / registration feature changes.
"""
from __future__ import annotations

import os
import sys
import uuid

from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.crud.user import user as crud_user
from app.database import SessionLocal
from app.main import app
from app.models.session import RefreshSession
from app.models.user import User
from app.models.user_status import UserStatus, UserRole


@pytest.fixture()
def authenticated_client():
    """Create a temporary user, log in, and yield an authenticated TestClient."""
    db = SessionLocal()
    email = f"smoke-{uuid.uuid4().hex[:12]}@example.com"
    password = "SmokeTest123!"

    db_user = User(
        email=email,
        hashed_password=crud_user.get_password_hash(password),
        full_name="Smoke Test User",
        is_active=True,
        is_superuser=False,
        is_verified=True,
        status=UserStatus.ACTIVE,
        role=UserRole.ADMIN,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    client = TestClient(app)
    # Login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, "remember_me": False},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"

    try:
        yield client
    finally:
        db.query(RefreshSession).filter(RefreshSession.user_id == db_user.id).delete()
        db.query(User).filter(User.id == db_user.id).delete()
        db.commit()
        db.close()


# ── Core Business Endpoints Smoke Tests ──

class TestCustomerSmoke:
    def test_list_customers(self, authenticated_client):
        resp = authenticated_client.get("/api/v1/customers")
        assert resp.status_code == 200
        data = resp.json()
        # Paginated response
        assert "items" in data or isinstance(data, list)

    def test_customer_detail_404(self, authenticated_client):
        fake_id = str(uuid.uuid4())
        resp = authenticated_client.get(f"/api/v1/customers/{fake_id}")
        assert resp.status_code in (404, 422)


class TestItemSmoke:
    def test_list_items(self, authenticated_client):
        resp = authenticated_client.get("/api/v1/catalog-items")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data or isinstance(data, list)

    def test_item_detail_404(self, authenticated_client):
        fake_id = str(uuid.uuid4())
        resp = authenticated_client.get(f"/api/v1/catalog-items/{fake_id}")
        assert resp.status_code in (404, 422)


class TestRfqSmoke:
    def test_list_rfqs(self, authenticated_client):
        resp = authenticated_client.get("/api/v1/rfqs")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list) or "items" in data

    def test_rfq_detail_404(self, authenticated_client):
        fake_id = str(uuid.uuid4())
        resp = authenticated_client.get(f"/api/v1/rfqs/{fake_id}")
        assert resp.status_code in (404, 422)


class TestQuoteSmoke:
    def test_list_quotes(self, authenticated_client):
        resp = authenticated_client.get("/api/v1/quotes")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list) or "items" in data

    def test_quote_detail_404(self, authenticated_client):
        fake_id = str(uuid.uuid4())
        resp = authenticated_client.get(f"/api/v1/quotes/{fake_id}")
        assert resp.status_code in (404, 422)
