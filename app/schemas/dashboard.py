from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel


class DashboardTrendPoint(BaseModel):
    label: str
    revenue: Decimal
    cost: Decimal
    margin_rate: Decimal

    mom_revenue: Optional[Decimal] = None
    yoy_revenue: Optional[Decimal] = None

    mom_cost: Optional[Decimal] = None
    yoy_cost: Optional[Decimal] = None

    mom_margin: Optional[Decimal] = None
    yoy_margin: Optional[Decimal] = None


class DashboardTrendResponse(BaseModel):
    granularity: Literal["month_day", "quarter_week", "year_month"]
    data: list[DashboardTrendPoint]
    has_more: bool
    earliest_confirmed_at: datetime | None = None
    resolved_period_start: datetime
    resolved_period_end: datetime
    previous_period_anchor: datetime | None = None
    next_period_anchor: datetime | None = None
    used_fallback: bool = False
