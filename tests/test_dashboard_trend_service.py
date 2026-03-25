from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.customer import Customer
from app.models.promotion import Promotion
from app.models.quote import Quote
from app.services.dashboard_trend import get_trend_data

UTC = timezone.utc
TAIPEI = ZoneInfo("Asia/Taipei")


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine, tables=[Customer.__table__, Promotion.__table__, Quote.__table__])
    db = testing_session_local()

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
        Base.metadata.drop_all(bind=engine, tables=[Quote.__table__, Promotion.__table__, Customer.__table__])


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


def _start_of_month(now: datetime) -> datetime:
    now_local = now.astimezone(TAIPEI)
    return datetime(now_local.year, now_local.month, 1, tzinfo=TAIPEI)


def _start_of_quarter(now: datetime) -> datetime:
    now_local = now.astimezone(TAIPEI)
    quarter_month = ((now_local.month - 1) // 3) * 3 + 1
    return datetime(now_local.year, quarter_month, 1, tzinfo=TAIPEI)


def _start_of_year(now: datetime) -> datetime:
    now_local = now.astimezone(TAIPEI)
    return datetime(now_local.year, 1, 1, tzinfo=TAIPEI)


def test_month_day_groups_by_day_and_sums_same_day_quotes(db_session: Session):
    now = datetime.now(UTC)
    month_start = _start_of_month(now)
    current_day = month_start + timedelta(days=2)
    previous_day = month_start + timedelta(days=1)

    _seed_quote(db_session, quote_id="day-1a", confirmed_at=current_day.astimezone(UTC), subtotal="1000", total_cost="600")
    _seed_quote(db_session, quote_id="day-1b", confirmed_at=(current_day + timedelta(hours=1)).astimezone(UTC), subtotal="500", total_cost="300")
    _seed_quote(db_session, quote_id="day-2", confirmed_at=previous_day.astimezone(UTC), subtotal="800", total_cost="400")
    _seed_quote(
        db_session,
        quote_id="day-yoy",
        confirmed_at=current_day.replace(year=current_day.year - 1).astimezone(UTC),
        subtotal="900",
        total_cost="450",
    )
    db_session.commit()

    result = get_trend_data(db_session, granularity="month_day", limit=12, before=None)

    assert result["granularity"] == "month_day"
    assert [row["label"] for row in result["data"][:2]] == [
        current_day.strftime("%m/%d"),
        previous_day.strftime("%m/%d"),
    ]
    current_bucket = result["data"][0]
    assert current_bucket["revenue"] == Decimal("1500.00")
    assert current_bucket["cost"] == Decimal("900.00")
    assert current_bucket["mom_revenue"] == Decimal("87.50")
    assert current_bucket["yoy_revenue"] == Decimal("66.67")


def test_quarter_week_groups_by_week_start(db_session: Session):
    now = datetime.now(UTC)
    quarter_start = _start_of_quarter(now)
    current_week = quarter_start + timedelta(days=7)
    current_week = current_week - timedelta(days=current_week.weekday())
    previous_week = current_week - timedelta(days=7)

    _seed_quote(db_session, quote_id="week-1a", confirmed_at=(current_week + timedelta(days=1)).astimezone(UTC), subtotal="700", total_cost="350")
    _seed_quote(db_session, quote_id="week-1b", confirmed_at=(current_week + timedelta(days=2)).astimezone(UTC), subtotal="300", total_cost="150")
    _seed_quote(db_session, quote_id="week-2", confirmed_at=(previous_week + timedelta(days=3)).astimezone(UTC), subtotal="400", total_cost="200")
    db_session.commit()

    result = get_trend_data(db_session, granularity="quarter_week", limit=12, before=None)

    assert result["granularity"] == "quarter_week"
    assert result["data"][0]["label"] == f"{current_week.strftime('%m/%d')} 週"
    assert result["data"][0]["revenue"] == Decimal("1000.00")
    assert result["data"][1]["label"] == f"{previous_week.strftime('%m/%d')} 週"


def test_year_month_groups_by_month(db_session: Session):
    now = datetime.now(UTC)
    current_month = datetime(now.year, now.month, 1, tzinfo=UTC)
    current_month = datetime(current_month.year, current_month.month, 1, tzinfo=TAIPEI)
    previous_month = datetime(current_month.year, max(1, current_month.month - 1), 1, tzinfo=TAIPEI)
    if now.month == 1:
        previous_month = _start_of_year(now)

    _seed_quote(db_session, quote_id="month-1a", confirmed_at=(current_month + timedelta(days=3)).astimezone(UTC), subtotal="1200", total_cost="700")
    _seed_quote(db_session, quote_id="month-1b", confirmed_at=(current_month + timedelta(days=4)).astimezone(UTC), subtotal="800", total_cost="500")
    _seed_quote(db_session, quote_id="month-2", confirmed_at=(previous_month + timedelta(days=2)).astimezone(UTC), subtotal="1000", total_cost="650")
    db_session.commit()

    result = get_trend_data(db_session, granularity="year_month", limit=12, before=None)

    assert result["granularity"] == "year_month"
    assert result["data"][0]["label"] == current_month.strftime("%Y-%m")
    assert result["data"][0]["revenue"] == Decimal("2000.00")
    if current_month != previous_month:
        assert result["data"][1]["label"] == previous_month.strftime("%Y-%m")


def test_closed_quotes_are_included_but_discarded_quotes_are_excluded(db_session: Session):
    now = datetime.now(UTC)
    month_start = _start_of_month(now)

    _seed_quote(db_session, quote_id="closed-keep", confirmed_at=(month_start + timedelta(days=5)).astimezone(UTC), subtotal="1500", total_cost="900", status="closed")
    _seed_quote(
        db_session,
        quote_id="discarded-ignore",
        confirmed_at=(month_start + timedelta(days=6)).astimezone(UTC),
        subtotal="999",
        total_cost="100",
        status="discarded",
    )
    db_session.commit()

    result = get_trend_data(db_session, granularity="month_day", limit=12, before=None)

    assert result["data"][0]["revenue"] == Decimal("1500.00")
    assert result["data"][0]["cost"] == Decimal("900.00")


def test_month_day_pagination_with_before(db_session: Session):
    now = datetime.now(UTC)
    month_start = _start_of_month(now)

    for offset in range(14):
        confirmed_at = (month_start + timedelta(days=offset)).astimezone(UTC)
        _seed_quote(
            db_session,
            quote_id=f"page-{offset}",
            confirmed_at=confirmed_at,
            subtotal="100",
            total_cost="50",
        )
    db_session.commit()

    page1 = get_trend_data(db_session, granularity="month_day", limit=12, before=None)
    assert len(page1["data"]) == 12
    assert page1["has_more"] is True
    assert page1["earliest_confirmed_at"] == month_start + timedelta(days=2)

    page2 = get_trend_data(
        db_session,
        granularity="month_day",
        limit=12,
        before=page1["earliest_confirmed_at"],
    )
    assert len(page2["data"]) == 2
    assert page2["has_more"] is False


def test_month_day_uses_taipei_timezone_for_bucket_cutoff(db_session: Session):
    # 2026-03-24 16:30 UTC == 2026-03-25 00:30 Asia/Taipei
    _seed_quote(
        db_session,
        quote_id="taipei-cutoff",
        confirmed_at=datetime(2026, 3, 24, 16, 30, tzinfo=UTC),
        subtotal="600",
        total_cost="300",
    )
    db_session.commit()

    result = get_trend_data(db_session, granularity="month_day", limit=12, before=None)

    labels = [row["label"] for row in result["data"]]
    assert "03/25" in labels


def test_month_day_earliest_confirmed_at_is_taipei_bucket_start_in_utc(db_session: Session):
    _seed_quote(
        db_session,
        quote_id="bucket-edge",
        confirmed_at=datetime(2026, 3, 24, 16, 30, tzinfo=UTC),
        subtotal="100",
        total_cost="50",
    )
    db_session.commit()

    result = get_trend_data(db_session, granularity="month_day", limit=12, before=None)

    assert result["earliest_confirmed_at"] == datetime(2026, 3, 24, 16, 0, tzinfo=UTC)
