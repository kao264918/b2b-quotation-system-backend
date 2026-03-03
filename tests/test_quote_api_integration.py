from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.crud.quote import QuoteValidationError
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


def _build_quote(cost_status: str = "ok") -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id="quote-1",
        quote_number="QUO-2603-001",
        rfq_id=None,
        customer_id="customer-1",
        title="Quote A",
        status="draft",
        accounting_status=None,
        version=1,
        tax_setting="taxable_5",
        subtotal=Decimal("1000.00"),
        tax_total=Decimal("50.00"),
        total=Decimal("1050.00"),
        cost_status=cost_status,
        total_cost=Decimal("700.00"),
        gross_profit_amount=Decimal("300.00"),
        gross_profit_rate=Decimal("30.00"),
        valid_until=None,
        notes=None,
        created_at=now,
        updated_at=now,
        sent_at=None,
        confirmed_at=None,
        items=[],
        customer=None,
    )


def test_quote_confirm_blocked_when_cost_incomplete(client, monkeypatch):
    from app.routers import quotes as quotes_router

    monkeypatch.setattr(quotes_router.crud.quote, "get", lambda db, id: _build_quote("missing"))

    def _raise_validation_error(db, quote, new_status):
        raise QuoteValidationError(
            "QUOTATION_COST_INCOMPLETE",
            "Quotation contains items without cost snapshot.",
            {"missing_item_ids": ["item-1", "item-2"]},
        )

    monkeypatch.setattr(quotes_router.crud.quote, "update_status", _raise_validation_error)

    response = client.patch(
        "/api/v1/quotes/quote-1/status",
        json={"status": "confirmed"},
        headers={"x-csrf-token": "test-token"},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "QUOTATION_COST_INCOMPLETE"
    assert detail["missing_item_ids"] == ["item-1", "item-2"]


def test_quote_list_passes_sorting_to_crud(client, monkeypatch):
    from app.routers import quotes as quotes_router

    captured = {}

    def _mock_get_multi(db, skip, limit, sort_by, sort_order):
        captured["skip"] = skip
        captured["limit"] = limit
        captured["sort_by"] = sort_by
        captured["sort_order"] = sort_order
        return []

    monkeypatch.setattr(quotes_router.crud.quote, "get_multi", _mock_get_multi)

    response = client.get("/api/v1/quotes?skip=10&limit=20&sort_by=total_cost&sort_order=asc")

    assert response.status_code == 200
    assert response.json() == []
    assert captured == {
        "skip": 10,
        "limit": 20,
        "sort_by": "total_cost",
        "sort_order": "asc",
    }


def test_internal_kpi_uses_range_parameter(client, monkeypatch):
    from app.routers import quotes as quotes_router

    captured = {}

    def _mock_get_internal_kpi(db, range_type):
        captured["range_type"] = range_type
        return {
            "range": range_type,
            "count": 3,
            "total_revenue_excl_tax": Decimal("3000.00"),
            "total_cost": Decimal("2100.00"),
            "average_gross_profit_rate": Decimal("30.00"),
        }

    monkeypatch.setattr(quotes_router.crud.quote, "get_internal_kpi", _mock_get_internal_kpi)

    response = client.get("/api/v1/quotes/internal-kpi?range=quarter")

    assert response.status_code == 200
    payload = response.json()
    assert payload["range"] == "quarter"
    assert payload["count"] == 3
    assert captured["range_type"] == "quarter"


def test_internal_kpi_denied_when_no_internal_cost_permission(client, monkeypatch):
    from app.routers import quotes as quotes_router

    monkeypatch.setattr(quotes_router, "can_view_internal_cost", lambda user: False)

    response = client.get("/api/v1/quotes/internal-kpi?range=month")
    assert response.status_code == 403
    assert response.json()["detail"] == "Permission denied"


def test_quote_list_masks_internal_cost_fields_without_permission(client, monkeypatch):
    from app.routers import quotes as quotes_router

    monkeypatch.setattr(quotes_router, "can_view_internal_cost", lambda user: False)
    monkeypatch.setattr(
        quotes_router.crud.quote,
        "get_multi",
        lambda db, skip=0, limit=100, sort_by=None, sort_order="desc": [_build_quote("ok")],
    )

    response = client.get("/api/v1/quotes")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["total_cost"] is None
    assert payload[0]["gross_profit_amount"] is None
    assert payload[0]["gross_profit_rate"] is None
