from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.crud.invoice import invoice as invoice_crud
from app.database import Base
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceItem
from app.models.quote import Quote, QuoteItem
from app.models.rfq import RFQ


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(
        bind=engine,
        tables=[
            Customer.__table__,
            RFQ.__table__,
            Quote.__table__,
            QuoteItem.__table__,
            Invoice.__table__,
            InvoiceItem.__table__,
        ],
    )

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(
            bind=engine,
            tables=[
                InvoiceItem.__table__,
                Invoice.__table__,
                QuoteItem.__table__,
                Quote.__table__,
                RFQ.__table__,
                Customer.__table__,
            ],
        )


def _seed_customer(db: Session) -> None:
    db.add(
        Customer(
            id="customer-1",
            company_name="ACME",
            tax_id="12345678",
            address_line1="Address 1",
            city="Taipei",
            country="TW",
            contact_name="Kevin",
            contact_email="kevin@example.com",
            roles=["customer"],
            status="active",
        )
    )
    db.commit()


def _seed_rfq(db: Session) -> None:
    db.add(
        RFQ(
            id="rfq-1",
            rfq_no="RFQ-001",
            project_name="Project A",
            vendor_id="customer-1",
            status="draft",
            accounting_status="unfulfilled",
        )
    )
    db.commit()


def _seed_confirmed_quote(db: Session) -> Quote:
    quote = Quote(
        id="quote-1",
        quote_number="QUO-001",
        customer_id="customer-1",
        rfq_id="rfq-1",
        title="Confirmed Quote",
        status="confirmed",
        tax_setting="taxable_5",
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
        confirmed_at=datetime.now(timezone.utc),
    )
    db.add(quote)
    db.flush()
    db.add(
        QuoteItem(
            id="quote-item-1",
            quote_id=quote.id,
            name="Line 1",
            description=None,
            quantity=Decimal("2"),
            unit="pcs",
            unit_price=Decimal("500.00"),
            tax_category_name="taxable_5",
            tax_rate=Decimal("0.05"),
            subtotal=Decimal("1000.00"),
            tax_amount=Decimal("45.00"),
            total_amount=Decimal("945.00"),
            line_total=Decimal("945.00"),
            snapshot_cost=Decimal("60.00"),
        )
    )
    db.commit()
    db.refresh(quote)
    return quote


def test_create_from_quote_blocks_duplicate_active_invoice(db_session: Session):
    _seed_customer(db_session)
    _seed_rfq(db_session)
    quote = _seed_confirmed_quote(db_session)

    first_invoice = invoice_crud.create_from_quote(db_session, quote=quote)
    assert first_invoice.quote_id == quote.id

    with pytest.raises(ValueError) as exc:
        invoice_crud.create_from_quote(db_session, quote=quote)

    assert str(exc.value) == "此報價單已建立請款單"


def test_create_from_quote_allows_recreate_after_soft_delete(db_session: Session):
    _seed_customer(db_session)
    _seed_rfq(db_session)
    quote = _seed_confirmed_quote(db_session)

    first_invoice = invoice_crud.create_from_quote(db_session, quote=quote)
    invoice_crud.soft_delete(db_session, invoice=first_invoice)

    second_invoice = invoice_crud.create_from_quote(db_session, quote=quote)

    assert second_invoice.id != first_invoice.id
    assert second_invoice.quote_id == quote.id


def test_update_status_draft_to_issued_sets_issued_at_and_unpaid(db_session: Session):
    _seed_customer(db_session)
    _seed_rfq(db_session)
    quote = _seed_confirmed_quote(db_session)
    invoice = invoice_crud.create_from_quote(db_session, quote=quote)

    updated = invoice_crud.update_status(db_session, invoice=invoice, new_status="issued")

    assert updated.status == "issued"
    assert updated.issued_at is not None
    assert updated.accounting_status == "unpaid"


def test_update_status_issued_to_paid_sets_paid_at_and_paid_accounting_status(db_session: Session):
    _seed_customer(db_session)
    _seed_rfq(db_session)
    quote = _seed_confirmed_quote(db_session)
    invoice = invoice_crud.create_from_quote(db_session, quote=quote)
    issued = invoice_crud.update_status(db_session, invoice=invoice, new_status="issued")

    paid = invoice_crud.update_status(db_session, invoice=issued, new_status="paid")

    assert paid.status == "paid"
    assert paid.issued_at is not None
    assert paid.paid_at is not None
    assert paid.accounting_status == "paid"


def test_update_status_issued_to_draft_sets_unpaid_and_keeps_issued_at(db_session: Session):
    _seed_customer(db_session)
    _seed_rfq(db_session)
    quote = _seed_confirmed_quote(db_session)
    invoice = invoice_crud.create_from_quote(db_session, quote=quote)
    issued = invoice_crud.update_status(db_session, invoice=invoice, new_status="issued")
    issued_at = issued.issued_at

    reverted = invoice_crud.update_status(db_session, invoice=issued, new_status="draft")

    assert reverted.status == "draft"
    assert reverted.accounting_status == "unpaid"
    assert reverted.issued_at == issued_at


def test_update_status_rejects_draft_to_paid(db_session: Session):
    _seed_customer(db_session)
    _seed_rfq(db_session)
    quote = _seed_confirmed_quote(db_session)
    invoice = invoice_crud.create_from_quote(db_session, quote=quote)

    with pytest.raises(ValueError) as exc:
        invoice_crud.update_status(db_session, invoice=invoice, new_status="paid")

    assert str(exc.value) == "無效的狀態轉換：draft → paid"


def test_update_status_allows_draft_to_void(db_session: Session):
    _seed_customer(db_session)
    _seed_rfq(db_session)
    quote = _seed_confirmed_quote(db_session)
    invoice = invoice_crud.create_from_quote(db_session, quote=quote)

    updated = invoice_crud.update_status(db_session, invoice=invoice, new_status="void")

    assert updated.status == "void"


def test_update_status_paid_to_issued_sets_unpaid_and_keeps_paid_at(db_session: Session):
    _seed_customer(db_session)
    _seed_rfq(db_session)
    quote = _seed_confirmed_quote(db_session)
    invoice = invoice_crud.create_from_quote(db_session, quote=quote)
    issued = invoice_crud.update_status(db_session, invoice=invoice, new_status="issued")
    paid = invoice_crud.update_status(db_session, invoice=issued, new_status="paid")
    paid_at = paid.paid_at

    reverted = invoice_crud.update_status(db_session, invoice=paid, new_status="issued")

    assert reverted.status == "issued"
    assert reverted.accounting_status == "unpaid"
    assert reverted.paid_at == paid_at


def test_update_status_rejects_paid_to_draft(db_session: Session):
    _seed_customer(db_session)
    _seed_rfq(db_session)
    quote = _seed_confirmed_quote(db_session)
    invoice = invoice_crud.create_from_quote(db_session, quote=quote)
    issued = invoice_crud.update_status(db_session, invoice=invoice, new_status="issued")
    paid = invoice_crud.update_status(db_session, invoice=issued, new_status="paid")

    with pytest.raises(ValueError) as exc:
        invoice_crud.update_status(db_session, invoice=paid, new_status="draft")

    assert str(exc.value) == "無效的狀態轉換：paid → draft"


def test_update_accounting_status_paid_maps_to_paid_status(db_session: Session):
    _seed_customer(db_session)
    _seed_rfq(db_session)
    quote = _seed_confirmed_quote(db_session)
    invoice = invoice_crud.create_from_quote(db_session, quote=quote)
    issued = invoice_crud.update_status(db_session, invoice=invoice, new_status="issued")

    updated = invoice_crud.update_accounting_status(db_session, invoice=issued, new_status="paid")

    assert updated.status == "paid"
    assert updated.accounting_status == "paid"
    assert updated.paid_at is not None


def test_update_accounting_status_unpaid_maps_paid_to_issued(db_session: Session):
    _seed_customer(db_session)
    _seed_rfq(db_session)
    quote = _seed_confirmed_quote(db_session)
    invoice = invoice_crud.create_from_quote(db_session, quote=quote)
    issued = invoice_crud.update_status(db_session, invoice=invoice, new_status="issued")
    paid = invoice_crud.update_status(db_session, invoice=issued, new_status="paid")

    updated = invoice_crud.update_accounting_status(db_session, invoice=paid, new_status="unpaid")

    assert updated.status == "issued"
    assert updated.accounting_status == "unpaid"
    assert updated.paid_at is not None


def test_update_accounting_status_unpaid_is_rejected_for_non_paid_invoice(db_session: Session):
    _seed_customer(db_session)
    _seed_rfq(db_session)
    quote = _seed_confirmed_quote(db_session)
    invoice = invoice_crud.create_from_quote(db_session, quote=quote)

    with pytest.raises(ValueError) as exc:
        invoice_crud.update_accounting_status(db_session, invoice=invoice, new_status="unpaid")

    assert str(exc.value) == "只有已付款的請款單可以撤銷付款"
