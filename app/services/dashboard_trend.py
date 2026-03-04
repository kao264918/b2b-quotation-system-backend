from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from sqlalchemy import Integer, and_, case, extract, func
from sqlalchemy.orm import Session

from app.models.quote import Quote

TrendGranularity = Literal["month", "quarter", "year"]

PERCENT_ZERO = Decimal("0.00")
PERCENT_Q = Decimal("0.01")


@dataclass(frozen=True)
class PeriodAggregate:
    year: int
    month: int | None
    quarter: int | None
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


def _period_label(period: PeriodAggregate, granularity: TrendGranularity) -> str:
    if granularity == "month":
        assert period.month is not None
        return f"{period.year:04d}-{period.month:02d}"
    if granularity == "quarter":
        assert period.quarter is not None
        return f"{period.year:04d}-Q{period.quarter}"
    return f"{period.year:04d}"


def _period_start(period: PeriodAggregate, granularity: TrendGranularity) -> datetime:
    if granularity == "month":
        assert period.month is not None
        return datetime(period.year, period.month, 1, tzinfo=timezone.utc)
    if granularity == "quarter":
        assert period.quarter is not None
        month = (period.quarter - 1) * 3 + 1
        return datetime(period.year, month, 1, tzinfo=timezone.utc)
    return datetime(period.year, 1, 1, tzinfo=timezone.utc)


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


def _previous_key(period: PeriodAggregate, granularity: TrendGranularity) -> tuple[int, int | None, int | None] | None:
    if granularity == "year":
        return None
    if granularity == "month":
        assert period.month is not None
        if period.month == 1:
            return (period.year - 1, 12, None)
        return (period.year, period.month - 1, None)
    assert period.quarter is not None
    if period.quarter == 1:
        return (period.year - 1, None, 4)
    return (period.year, None, period.quarter - 1)


def _yoy_key(period: PeriodAggregate, granularity: TrendGranularity) -> tuple[int, int | None, int | None]:
    if granularity == "month":
        assert period.month is not None
        return (period.year - 1, period.month, None)
    if granularity == "quarter":
        assert period.quarter is not None
        return (period.year - 1, None, period.quarter)
    return (period.year - 1, None, None)


def get_trend_data(
    db: Session,
    *,
    granularity: TrendGranularity,
    limit: int,
    before: datetime | None,
) -> dict:
    safe_limit = max(1, min(limit, 12))
    safe_before = before
    if safe_before is not None and safe_before.tzinfo is None:
        safe_before = safe_before.replace(tzinfo=timezone.utc)

    year_expr = extract("year", Quote.confirmed_at).cast(Integer)
    month_expr = extract("month", Quote.confirmed_at).cast(Integer)
    quarter_expr = case(
        (month_expr <= 3, 1),
        (month_expr <= 6, 2),
        (month_expr <= 9, 3),
        else_=4,
    )

    filters = [
        Quote.status == "confirmed",
        Quote.confirmed_at.is_not(None),
    ]

    if safe_before is not None:
        filters.append(Quote.confirmed_at < safe_before)

    base_columns = [
        func.coalesce(func.sum(Quote.subtotal), 0).label("period_revenue"),
        func.coalesce(func.sum(Quote.total_cost), 0).label("period_cost"),
    ]

    if granularity == "month":
        rows = (
            db.query(
                year_expr.label("period_year"),
                month_expr.label("period_month"),
                *base_columns,
            )
            .filter(*filters)
            .group_by(year_expr, month_expr)
            .order_by(year_expr.desc(), month_expr.desc())
            .all()
        )
    elif granularity == "quarter":
        rows = (
            db.query(
                year_expr.label("period_year"),
                quarter_expr.label("period_quarter"),
                *base_columns,
            )
            .filter(*filters)
            .group_by(year_expr, quarter_expr)
            .order_by(year_expr.desc(), quarter_expr.desc())
            .all()
        )
    else:
        rows = (
            db.query(
                year_expr.label("period_year"),
                *base_columns,
            )
            .filter(*filters)
            .group_by(year_expr)
            .order_by(year_expr.desc())
            .all()
        )

    aggregates: list[PeriodAggregate] = []
    for row in rows:
        month: int | None = None
        quarter: int | None = None
        if granularity == "month":
            month = int(row.period_month)
        elif granularity == "quarter":
            quarter = int(row.period_quarter)

        aggregates.append(
            PeriodAggregate(
                year=int(row.period_year),
                month=month,
                quarter=quarter,
                revenue=_q2(_to_decimal(row.period_revenue)),
                cost=_q2(_to_decimal(row.period_cost)),
            )
        )

    has_more = len(aggregates) > safe_limit
    current_page = aggregates[:safe_limit]

    value_map: dict[tuple[int, int | None, int | None], PeriodAggregate] = {}
    for item in aggregates:
        value_map[(item.year, item.month, item.quarter)] = item

    data: list[dict] = []
    for period in current_page:
        prev_key = _previous_key(period, granularity)
        yoy_key = _yoy_key(period, granularity)
        prev = value_map.get(prev_key) if prev_key is not None else None
        yoy = value_map.get(yoy_key)

        margin = _period_margin(period.revenue, period.cost)
        point = {
            "label": _period_label(period, granularity),
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
        if granularity == "year":
            point["mom_revenue"] = None
            point["mom_cost"] = None
            point["mom_margin"] = None
        data.append(point)

    earliest_confirmed_at: datetime | None = None
    if current_page:
        earliest_confirmed_at = _period_start(current_page[-1], granularity)

    return {
        "granularity": granularity,
        "data": data,
        "has_more": has_more,
        "earliest_confirmed_at": earliest_confirmed_at,
    }
