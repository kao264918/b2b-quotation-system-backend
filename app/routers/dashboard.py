from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.services.dashboard_trend import get_trend_data

router = APIRouter()

DashboardTrendGranularity = Literal["month_day", "quarter_week", "year_month"]

_LEGACY_TO_CANONICAL: dict[str, DashboardTrendGranularity] = {
    "month": "month_day",
    "quarter": "quarter_week",
    "year": "year_month",
}
_CANONICAL_VALUES = {"month_day", "quarter_week", "year_month"}


def _normalize_granularity(value: str) -> DashboardTrendGranularity:
    if value in _CANONICAL_VALUES:
        return value  # type: ignore[return-value]
    mapped = _LEGACY_TO_CANONICAL.get(value)
    if mapped is not None:
        return mapped
    raise HTTPException(
        status_code=422,
        detail=(
            "Invalid granularity. Expected one of: "
            "month_day, quarter_week, year_month, month, quarter, year"
        ),
    )


@router.get("/trend", response_model=schemas.DashboardTrendResponse)
def read_dashboard_trend(
    *,
    db: Session = Depends(get_db),
    granularity: str = Query(...),
    limit: int = Query(12, ge=1),
    before: datetime | None = Query(None),
):
    normalized_granularity = _normalize_granularity(granularity)
    return get_trend_data(
        db,
        granularity=normalized_granularity,
        limit=limit,
        before=before,
    )
