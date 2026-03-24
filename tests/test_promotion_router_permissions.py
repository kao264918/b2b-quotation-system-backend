from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.deps.auth import get_current_user
from app.main import app


@pytest.fixture()
def client():
    def override_db():
        yield SimpleNamespace()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_promotion_list_allows_owner_management_access(client, monkeypatch):
    from app.routers import promotions as promotions_router

    def override_current_user():
        return SimpleNamespace(id="user-1", is_superuser=False, role="owner")

    monkeypatch.setattr(promotions_router.crud.promotion, "get_multi_filtered", lambda *args, **kwargs: [])
    app.dependency_overrides[get_db] = lambda: iter([SimpleNamespace()])
    app.dependency_overrides[get_current_user] = override_current_user

    response = client.get("/api/v1/promotions?status=all")

    assert response.status_code == 200
    assert response.json() == []


def test_promotion_list_rejects_member_management_access(client, monkeypatch):
    from app.routers import promotions as promotions_router

    def override_current_user():
        return SimpleNamespace(id="user-1", is_superuser=False, role="member")

    monkeypatch.setattr(promotions_router.crud.promotion, "get_multi_filtered", lambda *args, **kwargs: [])
    app.dependency_overrides[get_db] = lambda: iter([SimpleNamespace()])
    app.dependency_overrides[get_current_user] = override_current_user

    response = client.get("/api/v1/promotions?status=all")

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized"
