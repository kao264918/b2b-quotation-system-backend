from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.customer import Customer
from app.models.quote import Quote
from app.services.dashboard_trend import get_trend_data


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine, tables=[Customer.__table__, Quote.__table__])
    db = TestingSessionLocal()

    customer = Customer(
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
    db.add(customer)
    db.commit()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine, tables=[Quote.__table__, Customer.__table__])


def _seed_quote(
    db: Session,
    *,
    quote_id: str,
    confirmed_at: datetime | None,
    subtotal: str,
    total_cost: str,
    status: str = "confirmed",
) -> None:
    quote = Quote(
        id=quote_id,
        quote_number=f"QUO-{quote_id}",
        customer_id="customer-1",
        rfq_id=None,
        title=quote_id,
        status=status,
        tax_setting="taxable_5",
        subtotal=Decimal(subtotal),
        tax_total=Decimal("0"),
        total=Decimal(subtotal),
        cost_status="ok",
        total_cost=Decimal(total_cost),
        gross_profit_amount=Decimal(subtotal) - Decimal(total_cost),
        gross_profit_rate=Decimal("0"),
        confirmed_at=confirmed_at,
    )
    db.add(quote)


def test_month_aggregation_growth_and_filters(db_session: Session):
    _seed_quote(
        db_session,
        quote_id="m202406",
        confirmed_at=datetime(2024, 6, 15, tzinfo=timezone.utc),
        subtotal="1200",
        total_cost="800",
    )
    _seed_quote(
        db_session,
        quote_id="m202405",
        confirmed_at=datetime(2024, 5, 20, tzinfo=timezone.utc),
        subtotal="1000",
        total_cost="850",
    )
    _seed_quote(
        db_session,
        quote_id="m202306",
        confirmed_at=datetime(2023, 6, 10, tzinfo=timezone.utc),
        subtotal="900",
        total_cost="700",
    )
    _seed_quote(
        db_session,
        quote_id="draft_ignore",
        confirmed_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        subtotal="999",
        total_cost="100",
        status="draft",
    )
    _seed_quote(
        db_session,
        quote_id="null_ignore",
        confirmed_at=None,
        subtotal="1000",
        total_cost="100",
    )
    db_session.commit()

    result = get_trend_data(
        db_session,
        granularity="month",
        limit=12,
        before=None,
    )

    assert result["granularity"] == "month"
    assert [row["label"] for row in result["data"]][:3] == ["2024-06", "2024-05", "2023-06"]
    june = result["data"][0]
    assert june["revenue"] == Decimal("1200.00")
    assert june["cost"] == Decimal("800.00")
    assert june["margin_rate"] == Decimal("33.33")
    assert june["mom_revenue"] == Decimal("20.00")
    assert june["yoy_revenue"] == Decimal("33.33")


def test_quarter_and_year_rules(db_session: Session):
    _seed_quote(
        db_session,
        quote_id="q1a",
        confirmed_at=datetime(2024, 1, 10, tzinfo=timezone.utc),
        subtotal="400",
        total_cost="200",
    )
    _seed_quote(
        db_session,
        quote_id="q1b",
        confirmed_at=datetime(2024, 3, 10, tzinfo=timezone.utc),
        subtotal="600",
        total_cost="300",
    )
    _seed_quote(
        db_session,
        quote_id="q4",
        confirmed_at=datetime(2023, 11, 10, tzinfo=timezone.utc),
        subtotal="500",
        total_cost="350",
    )
    _seed_quote(
        db_session,
        quote_id="y2022",
        confirmed_at=datetime(2022, 7, 10, tzinfo=timezone.utc),
        subtotal="200",
        total_cost="100",
    )
    db_session.commit()

    quarter_result = get_trend_data(
        db_session,
        granularity="quarter",
        limit=12,
        before=None,
    )
    assert quarter_result["data"][0]["label"] == "2024-Q1"
    assert quarter_result["data"][0]["revenue"] == Decimal("1000.00")
    assert quarter_result["data"][0]["yoy_revenue"] is None

    year_result = get_trend_data(
        db_session,
        granularity="year",
        limit=12,
        before=None,
    )
    first_year = year_result["data"][0]
    assert first_year["label"] == "2024"
    assert first_year["mom_revenue"] is None
    assert first_year["mom_cost"] is None
    assert first_year["mom_margin"] is None


def test_previous_zero_and_missing_yoy(db_session: Session):
    _seed_quote(
        db_session,
        quote_id="p202404",
        confirmed_at=datetime(2024, 4, 10, tzinfo=timezone.utc),
        subtotal="100",
        total_cost="20",
    )
    _seed_quote(
        db_session,
        quote_id="p202403",
        confirmed_at=datetime(2024, 3, 10, tzinfo=timezone.utc),
        subtotal="0",
        total_cost="0",
    )
    db_session.commit()

    result = get_trend_data(db_session, granularity="month", limit=12, before=None)
    april = result["data"][0]
    march = result["data"][1]

    assert april["label"] == "2024-04"
    assert april["mom_revenue"] == Decimal("0.00")
    assert april["mom_cost"] == Decimal("0.00")
    assert april["yoy_revenue"] is None
    assert march["mom_revenue"] is None


def test_pagination_has_more_and_before(db_session: Session):
    for i in range(14):
        month = 12 - (i % 12)
        year = 2025 - (i // 12)
        _seed_quote(
            db_session,
            quote_id=f"page{i + 1}",
            confirmed_at=datetime(year, month, 1, tzinfo=timezone.utc),
            subtotal="100",
            total_cost="50",
        )
    db_session.commit()

    page1 = get_trend_data(db_session, granularity="month", limit=12, before=None)
    assert len(page1["data"]) == 12
    assert page1["has_more"] is True
    assert page1["earliest_confirmed_at"] == datetime(2025, 1, 1, tzinfo=timezone.utc)

    page2 = get_trend_data(
        db_session,
        granularity="month",
        limit=12,
        before=page1["earliest_confirmed_at"],
    )
    assert len(page2["data"]) == 2
    assert page2["has_more"] is False
