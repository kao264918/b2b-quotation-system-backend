from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.database import get_db
from app.deps.auth import get_current_user
from app.main import app


def test_catalog_resolve_returns_requested_fields(monkeypatch):
    def override_db():
        yield SimpleNamespace()

    def override_current_user():
        return SimpleNamespace(id="test-user")

    def fake_get_multi_by_ids(db, *, ids):
        assert ids == ["item-1", "item-2"]
        return [
            SimpleNamespace(
                id="item-1",
                name="PVC Board",
                type="product",
                unit="pcs",
                category="board",
            ),
            SimpleNamespace(
                id="item-2",
                name="Install Service",
                type="service",
                unit="set",
                category=None,
            ),
        ]

    from app.routers import catalog as catalog_router_module

    monkeypatch.setattr(catalog_router_module.crud.catalog, "get_multi_by_ids", fake_get_multi_by_ids)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/catalog-items/resolve",
                json={"ids": ["item-1", "item-2"]},
                headers={"x-csrf-token": "test-token"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "item-1",
            "name": "PVC Board",
            "type": "product",
            "unit": "pcs",
            "category": "board",
        },
        {
            "id": "item-2",
            "name": "Install Service",
            "type": "service",
            "unit": "set",
            "category": None,
        },
    ]
