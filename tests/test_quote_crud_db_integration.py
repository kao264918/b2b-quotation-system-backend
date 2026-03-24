from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.crud.quote import QuoteValidationError, quote as quote_crud
from app.database import Base
from app.models.audit_log import AuditLog
from app.models.catalog import CatalogItem
from app.models.customer import Customer
from app.models.promotion import Promotion
from app.models.quote import Quote, QuoteItem
from app.models.rfq import RFQ
from app.schemas.quote import QuoteCreate


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
            CatalogItem.__table__,
            Promotion.__table__,
            RFQ.__table__,
            Quote.__table__,
            QuoteItem.__table__,
            AuditLog.__table__,
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
                QuoteItem.__table__,
                Quote.__table__,
                RFQ.__table__,
                Promotion.__table__,
                CatalogItem.__table__,
                Customer.__table__,
                AuditLog.__table__,
            ],
        )


def _seed_customer(db: Session, customer_id: str = "customer-1") -> Customer:
    customer = Customer(
        id=customer_id,
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
    db.add(customer)
    db.commit()
    return customer


def _seed_rfq(db: Session, rfq_id: str = "rfq-1", vendor_id: str = "customer-1") -> RFQ:
    rfq = RFQ(
        id=rfq_id,
        rfq_no=f"RFQ-{rfq_id}",
        project_name="RFQ Project",
        vendor_id=vendor_id,
        status="draft",
        accounting_status="unfulfilled",
    )
    db.add(rfq)
    db.commit()
    return rfq


def _seed_catalog_item(
    db: Session,
    item_id: str,
    item_no: str,
    reference_cost: Decimal,
) -> CatalogItem:
    item = CatalogItem(
        id=item_id,
        item_no=item_no,
        name=f"Item {item_no}",
        type="product",
        unit="pcs",
        reference_cost=reference_cost,
        default_price=Decimal("200.00"),
        status="active",
    )
    db.add(item)
    db.commit()
    return item


def _build_quote_create(
    customer_id: str,
    rfq_id: str,
    catalog_item_id: str,
    subtotal: Decimal = Decimal("1000.00"),
) -> QuoteCreate:
    return QuoteCreate(
        title="Integration Quote",
        rfq_id=rfq_id,
        customer_id=customer_id,
        tax_setting="taxable_5",
        subtotal=subtotal,
        tax_total=Decimal("50.00"),
        total=subtotal + Decimal("50.00"),
        items=[
            {
                "name": "Line 1",
                "quantity": Decimal("2"),
                "unit": "pcs",
                "unit_price": Decimal("500.00"),
                "tax_category_name": "taxable_5",
                "tax_rate": Decimal("0.05"),
                "subtotal": subtotal,
                "tax_amount": Decimal("50.00"),
                "total_amount": subtotal + Decimal("50.00"),
                "line_total": subtotal + Decimal("50.00"),
                "catalog_item_id": catalog_item_id,
            }
        ],
    )


def test_confirm_blocks_quote_with_missing_snapshot_cost(db_session: Session):
    _seed_customer(db_session)
    _seed_rfq(db_session)

    quote = Quote(
        id="quote-missing",
        quote_number="QUO-2603-900",
        customer_id="customer-1",
        rfq_id="rfq-1",
        title="Missing Cost Quote",
        status="draft",
        tax_setting="taxable_5",
        subtotal=Decimal("100.00"),
        tax_total=Decimal("5.00"),
        total=Decimal("105.00"),
        cost_status="missing",
        total_cost=Decimal("0.00"),
        gross_profit_amount=Decimal("100.00"),
        gross_profit_rate=Decimal("100.00"),
    )
    db_session.add(quote)
    db_session.flush()
    db_session.add(
        QuoteItem(
            id="item-missing",
            quote_id=quote.id,
            name="Legacy Item",
            quantity=Decimal("1"),
            unit="pcs",
            unit_price=Decimal("100.00"),
            tax_category_name="taxable_5",
            tax_rate=Decimal("0.05"),
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("5.00"),
            total_amount=Decimal("105.00"),
            line_total=Decimal("105.00"),
            snapshot_cost=None,
        )
    )
    db_session.commit()
    db_session.refresh(quote)

    with pytest.raises(QuoteValidationError) as exc:
        quote_crud.update_status(db_session, quote=quote, new_status="confirmed")

    assert exc.value.code == "QUOTATION_COST_INCOMPLETE"
    assert exc.value.extra["missing_item_ids"] == ["item-missing"]


def test_confirm_blocks_expired_quote_valid_until(db_session: Session):
    _seed_customer(db_session)
    _seed_rfq(db_session)
    _seed_catalog_item(db_session, "catalog-1", "ITEM-001", Decimal("60.00"))

    quote_in = _build_quote_create("customer-1", "rfq-1", "catalog-1")
    quote_in.valid_until = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=1)
    created = quote_crud.create(db_session, obj_in=quote_in)

    with pytest.raises(QuoteValidationError) as exc:
        quote_crud.update_status(db_session, quote=created, new_status="confirmed")

    assert exc.value.code == "QUOTATION_EXPIRED"


def test_revert_keeps_quote_editable_when_live_promotion_is_no_longer_valid(db_session: Session):
    _seed_customer(db_session)
    _seed_rfq(db_session)
    _seed_catalog_item(db_session, "catalog-1", "ITEM-001", Decimal("60.00"))

    promotion = Promotion(
        id="promo-1",
        promotion_code="PROMO-2603-001",
        promotion_name="Spring Promo",
        type="percentage",
        discount_value=Decimal("10.00"),
        minimum_order_amount=Decimal("0.00"),
        scope="all_products",
        scope_category=None,
        start_at=datetime.now(timezone.utc) - timedelta(days=1),
        end_at=datetime.now(timezone.utc) + timedelta(days=7),
        is_active=True,
    )
    db_session.add(promotion)
    db_session.commit()

    quote_in = _build_quote_create("customer-1", "rfq-1", "catalog-1")
    quote_in.promotion_id = promotion.id
    created = quote_crud.create(db_session, obj_in=quote_in)
    confirmed = quote_crud.update_status(db_session, quote=created, new_status="confirmed")

    promotion.is_active = False
    db_session.add(promotion)
    db_session.commit()
    db_session.refresh(confirmed)

    reverted = quote_crud.revert_quote(db_session, quote=confirmed)

    assert reverted.status == "draft"
    assert reverted.accounting_status is None
    assert reverted.confirmed_at is None
    assert reverted.promotion_id == promotion.id
    assert reverted.promotion_code_snapshot is None
    assert reverted.promotion_name_snapshot is None
    assert reverted.promotion_discount_amount == Decimal("0.00")
    assert reverted.tax_total == Decimal("50.00")
    assert reverted.total == Decimal("1050.00")


def test_get_multi_sorting_puts_missing_cost_last(db_session: Session):
    _seed_customer(db_session)
    _seed_rfq(db_session)

    q_ok_low = Quote(
        id="q-ok-low",
        quote_number="QUO-2603-001",
        customer_id="customer-1",
        rfq_id="rfq-1",
        title="OK Low",
        status="draft",
        tax_setting="taxable_5",
        subtotal=Decimal("1000.00"),
        tax_total=Decimal("50.00"),
        total=Decimal("1050.00"),
        cost_status="ok",
        total_cost=Decimal("400.00"),
        gross_profit_amount=Decimal("600.00"),
        gross_profit_rate=Decimal("60.00"),
    )
    q_ok_high = Quote(
        id="q-ok-high",
        quote_number="QUO-2603-002",
        customer_id="customer-1",
        rfq_id="rfq-1",
        title="OK High",
        status="draft",
        tax_setting="taxable_5",
        subtotal=Decimal("1000.00"),
        tax_total=Decimal("50.00"),
        total=Decimal("1050.00"),
        cost_status="ok",
        total_cost=Decimal("900.00"),
        gross_profit_amount=Decimal("100.00"),
        gross_profit_rate=Decimal("10.00"),
    )
    q_missing = Quote(
        id="q-missing",
        quote_number="QUO-2603-003",
        customer_id="customer-1",
        rfq_id="rfq-1",
        title="Missing",
        status="draft",
        tax_setting="taxable_5",
        subtotal=Decimal("1000.00"),
        tax_total=Decimal("50.00"),
        total=Decimal("1050.00"),
        cost_status="missing",
        total_cost=Decimal("0.00"),
        gross_profit_amount=Decimal("0.00"),
        gross_profit_rate=Decimal("0.00"),
    )
    db_session.add_all([q_ok_high, q_missing, q_ok_low])
    db_session.commit()

    rows = quote_crud.get_multi(
        db_session,
        skip=0,
        limit=10,
        sort_by="total_cost",
        sort_order="asc",
    )

    assert [q.id for q in rows] == ["q-ok-low", "q-ok-high", "q-missing"]


def test_internal_kpi_counts_confirmed_with_confirmed_at_range(db_session: Session):
    _seed_customer(db_session)
    _seed_rfq(db_session)

    now = datetime.now(timezone.utc)
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    last_quarter = datetime(
        now.year if now.month > 1 else now.year - 1,
        now.month - 1 if now.month > 1 else 12,
        15,
        tzinfo=timezone.utc,
    )

    in_month = Quote(
        id="q-kpi-month",
        quote_number="QUO-2603-101",
        customer_id="customer-1",
        rfq_id="rfq-1",
        title="KPI Month",
        status="confirmed",
        tax_setting="taxable_5",
        subtotal=Decimal("2000.00"),
        tax_total=Decimal("100.00"),
        total=Decimal("2100.00"),
        cost_status="ok",
        total_cost=Decimal("1200.00"),
        gross_profit_amount=Decimal("800.00"),
        gross_profit_rate=Decimal("40.00"),
        confirmed_at=month_start,
    )
    out_of_month = Quote(
        id="q-kpi-old",
        quote_number="QUO-2602-102",
        customer_id="customer-1",
        rfq_id="rfq-1",
        title="KPI Old",
        status="confirmed",
        tax_setting="taxable_5",
        subtotal=Decimal("1000.00"),
        tax_total=Decimal("50.00"),
        total=Decimal("1050.00"),
        cost_status="ok",
        total_cost=Decimal("700.00"),
        gross_profit_amount=Decimal("300.00"),
        gross_profit_rate=Decimal("30.00"),
        confirmed_at=last_quarter,
    )
    draft_quote = Quote(
        id="q-kpi-draft",
        quote_number="QUO-2603-103",
        customer_id="customer-1",
        rfq_id="rfq-1",
        title="KPI Draft",
        status="draft",
        tax_setting="taxable_5",
        subtotal=Decimal("5000.00"),
        tax_total=Decimal("250.00"),
        total=Decimal("5250.00"),
        cost_status="ok",
        total_cost=Decimal("3000.00"),
        gross_profit_amount=Decimal("2000.00"),
        gross_profit_rate=Decimal("40.00"),
        confirmed_at=month_start,
    )
    db_session.add_all([in_month, out_of_month, draft_quote])
    db_session.commit()

    month_kpi = quote_crud.get_internal_kpi(db_session, range_type="month")
    all_kpi = quote_crud.get_internal_kpi(db_session, range_type="all")

    assert month_kpi["count"] == 1
    assert month_kpi["total_revenue_excl_tax"] == Decimal("2000.00")
    assert month_kpi["total_cost"] == Decimal("1200.00")
    assert month_kpi["average_gross_profit_rate"] == Decimal("40.00")

    assert all_kpi["count"] == 2
    assert all_kpi["total_revenue_excl_tax"] == Decimal("3000.00")
    assert all_kpi["total_cost"] == Decimal("1900.00")
