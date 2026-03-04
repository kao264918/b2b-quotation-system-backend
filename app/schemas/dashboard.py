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
    granularity: Literal["month", "quarter", "year"]
    data: list[DashboardTrendPoint]
    has_more: bool
    earliest_confirmed_at: datetime | None = None
