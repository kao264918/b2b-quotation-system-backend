from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from sqlalchemy.orm import Session

from app.models.quote import Quote

TrendGranularity = Literal["month_day", "quarter_week", "year_month"]

PERCENT_ZERO = Decimal("0.00")
PERCENT_Q = Decimal("0.01")
UTC = timezone.utc


@dataclass(frozen=True)
class PeriodAggregate:
    key: str
    bucket_start: datetime
    label: str
    revenue: Decimal
    cost: Decimal


def _to_decimal(value: object) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _q2(value: Decimal) -> Decimal:
    return value.quantize(PERCENT_Q, rounding=ROUND_HALF_UP)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _start_of_month(value: datetime) -> datetime:
    value = _as_utc(value)
    return datetime(value.year, value.month, 1, tzinfo=UTC)


def _start_of_next_month(value: datetime) -> datetime:
    month_start = _start_of_month(value)
    if month_start.month == 12:
        return datetime(month_start.year + 1, 1, 1, tzinfo=UTC)
    return datetime(month_start.year, month_start.month + 1, 1, tzinfo=UTC)


def _start_of_quarter(value: datetime) -> datetime:
    value = _as_utc(value)
    quarter_month = ((value.month - 1) // 3) * 3 + 1
    return datetime(value.year, quarter_month, 1, tzinfo=UTC)


def _start_of_next_quarter(value: datetime) -> datetime:
    quarter_start = _start_of_quarter(value)
    if quarter_start.month == 10:
        return datetime(quarter_start.year + 1, 1, 1, tzinfo=UTC)
    return datetime(quarter_start.year, quarter_start.month + 3, 1, tzinfo=UTC)


def _start_of_year(value: datetime) -> datetime:
    value = _as_utc(value)
    return datetime(value.year, 1, 1, tzinfo=UTC)


def _start_of_next_year(value: datetime) -> datetime:
    year_start = _start_of_year(value)
    return datetime(year_start.year + 1, 1, 1, tzinfo=UTC)


def _shift_year(value: datetime, years: int) -> datetime:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(month=2, day=28, year=value.year + years)


def _shift_month(value: datetime, months: int) -> datetime:
    month_index = (value.month - 1) + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return datetime(year, month, 1, tzinfo=UTC)


def _bucket_start(value: datetime, granularity: TrendGranularity) -> datetime:
    value = _as_utc(value)
    if granularity == "month_day":
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    if granularity == "quarter_week":
        monday = value - timedelta(days=value.weekday())
        return datetime(monday.year, monday.month, monday.day, tzinfo=UTC)
    return datetime(value.year, value.month, 1, tzinfo=UTC)


def _format_label(bucket_start: datetime, granularity: TrendGranularity) -> str:
    if granularity == "month_day":
        return bucket_start.strftime("%m/%d")
    if granularity == "quarter_week":
        return f"{bucket_start.strftime('%m/%d')} 週"
    return bucket_start.strftime("%Y-%m")


def _period_margin(revenue: Decimal, cost: Decimal) -> Decimal:
    if revenue == 0:
        return PERCENT_ZERO
    return _q2((revenue - cost) / revenue * Decimal("100"))


def _growth(current: Decimal, previous: Decimal | None) -> Decimal | None:
    if previous is None:
        return None
    if previous == 0:
        return PERCENT_ZERO
    return _q2((current - previous) / previous * Decimal("100"))


def _previous_bucket_start(bucket_start: datetime, granularity: TrendGranularity) -> datetime | None:
    if granularity == "month_day":
        return bucket_start - timedelta(days=1)
    if granularity == "quarter_week":
        return bucket_start - timedelta(days=7)
    return _shift_month(bucket_start, -1)


def _yoy_bucket_start(bucket_start: datetime, granularity: TrendGranularity) -> datetime:
    if granularity == "quarter_week":
        return _shift_year(bucket_start, -1)
    return _shift_year(bucket_start, -1)


def _period_bounds(now: datetime, granularity: TrendGranularity) -> tuple[datetime, datetime, datetime, datetime]:
    if granularity == "month_day":
        current_start = _start_of_month(now)
        current_end = _start_of_next_month(now)
        comparison_start = _shift_year(current_start, -1)
        comparison_end = _shift_year(current_end, -1)
        return current_start, current_end, comparison_start, comparison_end
    if granularity == "quarter_week":
        current_start = _start_of_quarter(now)
        current_end = _start_of_next_quarter(now)
        comparison_start = _shift_year(current_start, -1)
        comparison_end = _shift_year(current_end, -1)
        return current_start, current_end, comparison_start, comparison_end
    current_start = _start_of_year(now)
    current_end = _start_of_next_year(now)
    comparison_start = _shift_year(current_start, -1)
    comparison_end = _shift_year(current_end, -1)
    return current_start, current_end, comparison_start, comparison_end


def _aggregate_quotes(quotes: list[Quote], granularity: TrendGranularity) -> dict[datetime, PeriodAggregate]:
    buckets: dict[datetime, dict[str, Decimal]] = {}
    for quote in quotes:
        confirmed_at = getattr(quote, "confirmed_at", None)
        if confirmed_at is None:
            continue
        bucket_start = _bucket_start(confirmed_at, granularity)
        entry = buckets.setdefault(bucket_start, {"revenue": Decimal("0"), "cost": Decimal("0")})
        entry["revenue"] += _to_decimal(getattr(quote, "subtotal", 0))
        entry["cost"] += _to_decimal(getattr(quote, "total_cost", 0))

    return {
        bucket_start: PeriodAggregate(
            key=bucket_start.isoformat(),
            bucket_start=bucket_start,
            label=_format_label(bucket_start, granularity),
            revenue=_q2(values["revenue"]),
            cost=_q2(values["cost"]),
        )
        for bucket_start, values in buckets.items()
    }


def get_trend_data(
    db: Session,
    *,
    granularity: TrendGranularity,
    limit: int,
    before: datetime | None,
) -> dict:
    safe_limit = max(1, min(limit, 12))
    safe_before = _as_utc(before) if before is not None else None
    now = datetime.now(UTC)
    current_start, current_end, comparison_start, comparison_end = _period_bounds(now, granularity)

    base_query = db.query(Quote).filter(
        Quote.confirmed_at.is_not(None),
        Quote.status.in_(["confirmed", "closed"]),
    )

    current_query = base_query.filter(
        Quote.confirmed_at >= current_start,
        Quote.confirmed_at < current_end,
    )
    if safe_before is not None:
        current_query = current_query.filter(Quote.confirmed_at < safe_before)

    comparison_query = base_query.filter(
        Quote.confirmed_at >= comparison_start,
        Quote.confirmed_at < comparison_end,
    )

    current_aggregates = _aggregate_quotes(current_query.all(), granularity)
    comparison_aggregates = _aggregate_quotes(comparison_query.all(), granularity)

    ordered_current = sorted(current_aggregates.values(), key=lambda item: item.bucket_start, reverse=True)
    has_more = len(ordered_current) > safe_limit
    current_page = ordered_current[:safe_limit]

    data: list[dict] = []
    for period in current_page:
        prev_start = _previous_bucket_start(period.bucket_start, granularity)
        yoy_start = _yoy_bucket_start(period.bucket_start, granularity)
        prev = current_aggregates.get(prev_start) if prev_start is not None else None
        yoy = comparison_aggregates.get(yoy_start)

        margin = _period_margin(period.revenue, period.cost)
        point = {
            "label": period.label,
            "revenue": period.revenue,
            "cost": period.cost,
            "margin_rate": margin,
            "mom_revenue": _growth(period.revenue, prev.revenue) if prev is not None else None,
            "yoy_revenue": _growth(period.revenue, yoy.revenue) if yoy is not None else None,
            "mom_cost": _growth(period.cost, prev.cost) if prev is not None else None,
            "yoy_cost": _growth(period.cost, yoy.cost) if yoy is not None else None,
            "mom_margin": _growth(margin, _period_margin(prev.revenue, prev.cost)) if prev is not None else None,
            "yoy_margin": _growth(margin, _period_margin(yoy.revenue, yoy.cost)) if yoy is not None else None,
        }
        data.append(point)

    earliest_confirmed_at = current_page[-1].bucket_start if current_page else None

    return {
        "granularity": granularity,
        "data": data,
        "has_more": has_more,
        "earliest_confirmed_at": earliest_confirmed_at,
    }
