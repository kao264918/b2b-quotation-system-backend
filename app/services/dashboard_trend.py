from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.quote import Quote

TrendGranularity = Literal["month_day", "quarter_week", "year_month"]

PERCENT_ZERO = Decimal("0.00")
PERCENT_Q = Decimal("0.01")
UTC = timezone.utc
TAIPEI = ZoneInfo("Asia/Taipei")


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


def _to_taipei(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC).astimezone(TAIPEI)
    return value.astimezone(TAIPEI)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=TAIPEI).astimezone(UTC)
    return value.astimezone(UTC)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _start_of_month_local(value: datetime) -> datetime:
    value = _to_taipei(value)
    return datetime(value.year, value.month, 1, tzinfo=TAIPEI)


def _start_of_next_month_local(value: datetime) -> datetime:
    month_start = _start_of_month_local(value)
    if month_start.month == 12:
        return datetime(month_start.year + 1, 1, 1, tzinfo=TAIPEI)
    return datetime(month_start.year, month_start.month + 1, 1, tzinfo=TAIPEI)


def _start_of_quarter_local(value: datetime) -> datetime:
    value = _to_taipei(value)
    quarter_month = ((value.month - 1) // 3) * 3 + 1
    return datetime(value.year, quarter_month, 1, tzinfo=TAIPEI)


def _start_of_next_quarter_local(value: datetime) -> datetime:
    quarter_start = _start_of_quarter_local(value)
    if quarter_start.month == 10:
        return datetime(quarter_start.year + 1, 1, 1, tzinfo=TAIPEI)
    return datetime(quarter_start.year, quarter_start.month + 3, 1, tzinfo=TAIPEI)


def _start_of_year_local(value: datetime) -> datetime:
    value = _to_taipei(value)
    return datetime(value.year, 1, 1, tzinfo=TAIPEI)


def _start_of_next_year_local(value: datetime) -> datetime:
    year_start = _start_of_year_local(value)
    return datetime(year_start.year + 1, 1, 1, tzinfo=TAIPEI)


def _shift_year(value: datetime, years: int) -> datetime:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(month=2, day=28, year=value.year + years)


def _shift_month(value: datetime, months: int) -> datetime:
    month_index = (value.month - 1) + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return datetime(year, month, 1, tzinfo=value.tzinfo or TAIPEI)


def _bucket_start_local(value: datetime, granularity: TrendGranularity) -> datetime:
    value = _to_taipei(value)
    if granularity == "month_day":
        return datetime(value.year, value.month, value.day, tzinfo=TAIPEI)
    if granularity == "quarter_week":
        monday = value - timedelta(days=value.weekday())
        return datetime(monday.year, monday.month, monday.day, tzinfo=TAIPEI)
    return datetime(value.year, value.month, 1, tzinfo=TAIPEI)


def _format_label(bucket_start_local: datetime, granularity: TrendGranularity) -> str:
    if granularity == "month_day":
        return bucket_start_local.strftime("%m/%d")
    if granularity == "quarter_week":
        return f"{bucket_start_local.strftime('%m/%d')} 週"
    return bucket_start_local.strftime("%Y-%m")


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


def _period_start_local(value: datetime, granularity: TrendGranularity) -> datetime:
    if granularity == "month_day":
        return _start_of_month_local(value)
    if granularity == "quarter_week":
        return _start_of_quarter_local(value)
    return _start_of_year_local(value)


def _next_period_start_local(period_start: datetime, granularity: TrendGranularity) -> datetime:
    if granularity == "month_day":
        return _start_of_next_month_local(period_start)
    if granularity == "quarter_week":
        return _start_of_next_quarter_local(period_start)
    return _start_of_next_year_local(period_start)


def _period_bounds_local(anchor: datetime, granularity: TrendGranularity) -> tuple[datetime, datetime, datetime, datetime]:
    current_start = _period_start_local(anchor, granularity)
    current_end = _next_period_start_local(current_start, granularity)
    comparison_start = _shift_year(current_start, -1)
    comparison_end = _shift_year(current_end, -1)
    return current_start, current_end, comparison_start, comparison_end


def _latest_confirmed_at(db: Session) -> datetime | None:
    return db.query(func.max(Quote.confirmed_at)).filter(
        Quote.confirmed_at.is_not(None),
        Quote.status.in_(["confirmed", "closed"]),
    ).scalar()


def _period_has_data(
    db: Session,
    *,
    period_start: datetime,
    period_end: datetime,
) -> bool:
    return (
        db.query(Quote.id)
        .filter(
            Quote.confirmed_at.is_not(None),
            Quote.status.in_(["confirmed", "closed"]),
            Quote.confirmed_at >= _to_utc(period_start),
            Quote.confirmed_at < _to_utc(period_end),
        )
        .first()
        is not None
    )


def _resolve_anchor(
    db: Session,
    *,
    granularity: TrendGranularity,
    anchor: datetime | None,
    auto_fallback: bool,
) -> tuple[datetime, bool]:
    if anchor is not None:
        return _period_start_local(anchor, granularity), False

    natural_anchor = _period_start_local(_now_utc(), granularity)
    natural_end = _next_period_start_local(natural_anchor, granularity)
    if _period_has_data(db, period_start=natural_anchor, period_end=natural_end):
        return natural_anchor, False

    if not auto_fallback:
        return natural_anchor, False

    latest_confirmed_at = _latest_confirmed_at(db)
    if latest_confirmed_at is None:
        return natural_anchor, False

    fallback_anchor = _period_start_local(latest_confirmed_at, granularity)
    return fallback_anchor, fallback_anchor != natural_anchor


def _period_nav(anchor: datetime, granularity: TrendGranularity) -> tuple[datetime, datetime]:
    if granularity == "month_day":
        return _shift_month(anchor, -1), _shift_month(anchor, 1)
    if granularity == "quarter_week":
        return _shift_month(anchor, -3), _shift_month(anchor, 3)
    return _shift_year(anchor, -1), _shift_year(anchor, 1)


def _aggregate_quotes(quotes: list[Quote], granularity: TrendGranularity) -> dict[datetime, PeriodAggregate]:
    buckets: dict[datetime, dict[str, Decimal]] = {}
    for quote in quotes:
        confirmed_at = getattr(quote, "confirmed_at", None)
        if confirmed_at is None:
            continue
        bucket_start_local = _bucket_start_local(confirmed_at, granularity)
        entry = buckets.setdefault(bucket_start_local, {"revenue": Decimal("0"), "cost": Decimal("0")})
        entry["revenue"] += _to_decimal(getattr(quote, "subtotal", 0))
        entry["cost"] += _to_decimal(getattr(quote, "total_cost", 0))

    return {
        bucket_start_local: PeriodAggregate(
            key=bucket_start_local.isoformat(),
            bucket_start=bucket_start_local,
            label=_format_label(bucket_start_local, granularity),
            revenue=_q2(values["revenue"]),
            cost=_q2(values["cost"]),
        )
        for bucket_start_local, values in buckets.items()
    }


def get_trend_data(
    db: Session,
    *,
    granularity: TrendGranularity,
    limit: int,
    before: datetime | None,
    anchor: datetime | None,
    auto_fallback: bool,
) -> dict:
    safe_limit = max(1, min(limit, 12))
    safe_before = _as_utc(before) if before is not None else None
    resolved_anchor_local, used_fallback = _resolve_anchor(
        db,
        granularity=granularity,
        anchor=anchor,
        auto_fallback=auto_fallback,
    )
    current_start_local, current_end_local, comparison_start_local, comparison_end_local = _period_bounds_local(
        resolved_anchor_local,
        granularity,
    )
    current_start = _to_utc(current_start_local)
    current_end = _to_utc(current_end_local)
    comparison_start = _to_utc(comparison_start_local)
    comparison_end = _to_utc(comparison_end_local)
    previous_period_anchor, next_period_anchor = _period_nav(resolved_anchor_local, granularity)

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

    earliest_confirmed_at = _to_utc(current_page[-1].bucket_start) if current_page else None

    return {
        "granularity": granularity,
        "data": data,
        "has_more": has_more,
        "earliest_confirmed_at": earliest_confirmed_at,
        "resolved_period_start": current_start,
        "resolved_period_end": current_end,
        "previous_period_anchor": _to_utc(previous_period_anchor),
        "next_period_anchor": _to_utc(next_period_anchor),
        "used_fallback": used_fallback,
    }
