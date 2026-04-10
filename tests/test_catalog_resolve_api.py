from decimal import Decimal
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

    def override_current_user():
        return SimpleNamespace(id="test-user")

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_current_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_catalog_resolve_returns_batch_metadata_and_price(client, monkeypatch):
    from app.routers import catalog as catalog_router

    monkeypatch.setattr(
        catalog_router.crud.catalog,
        "get_multi_by_ids",
        lambda db, ids: [
            SimpleNamespace(
                id="item-2",
                name="Catalog B",
                type="service",
                unit="set",
                category="labor",
                default_price=Decimal("2200.00"),
            ),
            SimpleNamespace(
                id="item-1",
                name="Catalog A",
                type="product",
                unit="pcs",
                category="panel",
                default_price=Decimal("1500.00"),
            ),
        ],
    )

    response = client.post(
        "/api/v1/catalog-items/resolve",
        json={"ids": ["item-1", "item-2", "missing-item"]},
        headers={"x-csrf-token": "test-token"},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "item-1",
            "name": "Catalog A",
            "type": "product",
            "unit": "pcs",
            "category": "panel",
            "default_price": "1500.00",
        },
        {
            "id": "item-2",
            "name": "Catalog B",
            "type": "service",
            "unit": "set",
            "category": "labor",
            "default_price": "2200.00",
        },
    ]
