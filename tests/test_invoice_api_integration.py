from datetime import datetime, timezone
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


def _build_confirmed_quote() -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id="quote-1",
        customer_id="customer-1",
        status="confirmed",
        subtotal=Decimal("1000.00"),
        promotion_discount_amount=Decimal("100.00"),
        promotion_code_snapshot="PROMO-2603-001",
        promotion_name_snapshot="Spring Promo",
        promotion_type_snapshot="percentage",
        promotion_value_snapshot=Decimal("10.00"),
        promotion_scope_snapshot="all_products",
        promotion_scope_category_snapshot=None,
        tax_total=Decimal("45.00"),
        total=Decimal("945.00"),
        notes="note",
        created_at=now,
        updated_at=now,
        items=[],
    )


def _build_invoice(status: str = "draft") -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id="invoice-1",
        invoice_number="INV-2603-0001",
        quote_id="quote-1",
        customer_id="customer-1",
        status=status,
        accounting_status="paid" if status == "paid" else "unpaid",
        subtotal=Decimal("1000.00"),
        promotion_discount_amount=Decimal("100.00"),
        promotion_code_snapshot="PROMO-2603-001",
        promotion_name_snapshot="Spring Promo",
        promotion_type_snapshot="percentage",
        promotion_value_snapshot=Decimal("10.00"),
        promotion_scope_snapshot="all_products",
        promotion_scope_category_snapshot=None,
        tax_total=Decimal("45.00"),
        total=Decimal("945.00"),
        notes="note",
        issued_at=now if status in {"issued", "paid"} else None,
        paid_at=now if status == "paid" else None,
        due_date=None,
        created_at=now,
        updated_at=now,
        deleted_at=None,
        items=[],
        customer=None,
        quote=None,
    )


def test_create_invoice_from_quote_rejects_duplicate_active_invoice(client, monkeypatch):
    from app.routers import invoices as invoices_router

    monkeypatch.setattr(invoices_router.crud.quote, "get", lambda db, id: _build_confirmed_quote())

    def _raise_duplicate(db, quote):
        raise ValueError("此報價單已建立請款單")

    monkeypatch.setattr(invoices_router.crud.invoice, "create_from_quote", _raise_duplicate)

    response = client.post(
        "/api/v1/invoices/from-quote",
        json={"quote_id": "quote-1"},
        headers={"x-csrf-token": "test-token"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "此報價單已建立請款單"


def test_read_invoices_passes_quote_id_filter(client, monkeypatch):
    from app.routers import invoices as invoices_router

    captured: dict[str, object] = {}

    def _mock_get_multi(db, skip=0, limit=100, include_deleted=False, quote_id=None, search=None):
        captured["skip"] = skip
        captured["limit"] = limit
        captured["include_deleted"] = include_deleted
        captured["quote_id"] = quote_id
        captured["search"] = search
        return [], 0

    monkeypatch.setattr(invoices_router.crud.invoice, "get_multi", _mock_get_multi)

    response = client.get("/api/v1/invoices?skip=0&limit=1&quote_id=quote-1&search=acme")

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "page": 1,
        "page_size": 1,
        "total": 0,
        "total_pages": 1,
    }
    assert captured == {
        "skip": 0,
        "limit": 1,
        "include_deleted": False,
        "quote_id": "quote-1",
        "search": "acme",
    }


def test_update_invoice_accounting_status_paid_maps_to_status_paid(client, monkeypatch):
    from app.routers import invoices as invoices_router

    invoice = _build_invoice("issued")
    expected = _build_invoice("paid")

    monkeypatch.setattr(invoices_router.crud.invoice, "get", lambda db, id: invoice)

    captured: dict[str, object] = {}

    def _mock_update_accounting_status(db, invoice, new_status):
        captured["invoice_id"] = invoice.id
        captured["new_status"] = new_status
        return expected

    monkeypatch.setattr(invoices_router.crud.invoice, "update_accounting_status", _mock_update_accounting_status)

    response = client.patch(
        "/api/v1/invoices/invoice-1/accounting-status",
        json={"accounting_status": "paid"},
        headers={"x-csrf-token": "test-token"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "paid"
    assert captured == {
        "invoice_id": "invoice-1",
        "new_status": "paid",
    }


def test_update_invoice_accounting_status_unpaid_rejected(client, monkeypatch):
    from app.routers import invoices as invoices_router

    invoice = _build_invoice("issued")
    monkeypatch.setattr(invoices_router.crud.invoice, "get", lambda db, id: invoice)

    def _raise_value_error(db, invoice, new_status):
        raise ValueError("請改用請款單狀態更新流程")

    monkeypatch.setattr(invoices_router.crud.invoice, "update_accounting_status", _raise_value_error)

    response = client.patch(
        "/api/v1/invoices/invoice-1/accounting-status",
        json={"accounting_status": "unpaid"},
        headers={"x-csrf-token": "test-token"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "請改用請款單狀態更新流程"


def test_update_invoice_accounting_status_unpaid_maps_paid_to_issued(client, monkeypatch):
    from app.routers import invoices as invoices_router

    invoice = _build_invoice("paid")
    expected = _build_invoice("issued")

    monkeypatch.setattr(invoices_router.crud.invoice, "get", lambda db, id: invoice)

    captured: dict[str, object] = {}

    def _mock_update_accounting_status(db, invoice, new_status):
        captured["invoice_id"] = invoice.id
        captured["new_status"] = new_status
        return expected

    monkeypatch.setattr(invoices_router.crud.invoice, "update_accounting_status", _mock_update_accounting_status)

    response = client.patch(
        "/api/v1/invoices/invoice-1/accounting-status",
        json={"accounting_status": "unpaid"},
        headers={"x-csrf-token": "test-token"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "issued"
    assert captured == {
        "invoice_id": "invoice-1",
        "new_status": "unpaid",
    }
