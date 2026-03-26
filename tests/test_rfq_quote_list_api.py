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
        return SimpleNamespace(id="test-user", is_superuser=True)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_current_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_rfq_list_returns_paginated_contract(client, monkeypatch):
    from app.routers import rfqs as rfqs_router

    monkeypatch.setattr(
        rfqs_router.rfq_crud,
        "get_rfq_list_rows",
        lambda db, **kwargs: [
            {
                "id": "rfq-1",
                "rfq_no": "RFQ-001",
                "project_name": "Project One",
                "vendor_name": "Vendor One",
                "status": "draft",
                "accounting_status": "unfulfilled",
                "subtotal": "100.00",
                "total_amount": "105.00",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-02T00:00:00Z",
            }
        ],
    )
    monkeypatch.setattr(rfqs_router.rfq_crud, "count_rfqs", lambda db, **kwargs: 25)

    response = client.get("/api/v1/rfqs?page=2&page_size=10")
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 2
    assert body["page_size"] == 10
    assert body["total"] == 25
    assert body["total_pages"] == 3
    assert body["items"][0]["rfq_no"] == "RFQ-001"


def test_quote_list_returns_paginated_contract(client, monkeypatch):
    from app.routers import quotes as quotes_router

    quote = SimpleNamespace(
        id="quote-1",
        quote_number="QUO-001",
        rfq_id=None,
        customer_id="customer-1",
        customer=None,
        title="Quote One",
        status="draft",
        accounting_status=None,
        version=1,
        tax_setting="taxable_5",
        subtotal="100.00",
        promotion_id=None,
        promotion_discount_amount="0.00",
        tax_total="5.00",
        total="105.00",
        cost_status="ok",
        total_cost="80.00",
        gross_profit_amount="20.00",
        gross_profit_rate="20.00",
        valid_until=None,
        notes=None,
        created_at="2025-01-01T00:00:00Z",
        updated_at="2025-01-02T00:00:00Z",
        sent_at=None,
        confirmed_at=None,
        items=[],
        applied_promotion=None,
    )

    monkeypatch.setattr(quotes_router.crud.quote, "get_multi", lambda db, **kwargs: [quote])
    monkeypatch.setattr(quotes_router.crud.quote, "count_multi", lambda db: 21)

    response = client.get("/api/v1/quotes?skip=10&limit=10")
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 2
    assert body["page_size"] == 10
    assert body["total"] == 21
    assert body["total_pages"] == 3
    assert body["items"][0]["quote_number"] == "QUO-001"
