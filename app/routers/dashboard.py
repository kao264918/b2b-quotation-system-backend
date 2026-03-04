from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.services.dashboard_trend import get_trend_data

router = APIRouter()


@router.get("/trend", response_model=schemas.DashboardTrendResponse)
def read_dashboard_trend(
    *,
    db: Session = Depends(get_db),
    granularity: Literal["month", "quarter", "year"] = Query(...),
    limit: int = Query(12, ge=1),
    before: datetime | None = Query(None),
):
    return get_trend_data(
        db,
        granularity=granularity,
        limit=limit,
        before=before,
    )
