from decimal import Decimal
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.deps.auth import get_current_user, require_superuser
from app.models.user import User
from app.services.promotion_pricing import (
    PromotionValidationError,
    get_promotion_runtime_status,
)

router = APIRouter()


def _require_promotion_admin(current_user: User) -> None:
    is_admin = current_user.is_superuser or getattr(current_user, "role", None) in ("owner", "admin")
    if not is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")


def _filter_by_status(items: list, status: Optional[str]) -> list:
    if not status or status == "all":
        return items
    return [item for item in items if get_promotion_runtime_status(item) == status]


@router.get("", response_model=List[schemas.Promotion])
def read_promotions(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
    status: str = Query("all"),
    eligible_only: bool = False,
    quote_subtotal: Decimal | None = None,
    quote_category_values: str | None = None,
) -> Any:
    promotions = crud.promotion.get_multi_filtered(
        db,
        skip=skip,
        limit=limit,
        search=search,
    )
    promotions = _filter_by_status(promotions, status)

    if not eligible_only:
        _require_promotion_admin(current_user)
        return promotions

    normalized_categories = {
        value.strip().lower()
        for value in (quote_category_values or "").split(",")
        if value.strip()
    }
    subtotal = Decimal(quote_subtotal or 0)
    eligible = []
    for item in promotions:
        runtime_status = get_promotion_runtime_status(item)
        if runtime_status != "active":
            continue
        if subtotal < Decimal(item.minimum_order_amount):
            continue
        if item.scope == "category":
            if not item.scope_category or item.scope_category.strip().lower() not in normalized_categories:
                continue
        eligible.append(item)
    return eligible


@router.post("", response_model=schemas.Promotion)
def create_promotion(
    *,
    db: Session = Depends(get_db),
    promotion_in: schemas.PromotionCreate,
    current_user: User = Depends(require_superuser),
) -> Any:
    _require_promotion_admin(current_user)
    return crud.promotion.create(db, obj_in=promotion_in)


@router.get("/{id}", response_model=schemas.Promotion)
def read_promotion(
    *,
    db: Session = Depends(get_db),
    id: str,
    current_user: User = Depends(require_superuser),
) -> Any:
    _require_promotion_admin(current_user)
    promotion = crud.promotion.get(db, id=id)
    if not promotion:
        raise HTTPException(status_code=404, detail="Promotion not found")
    return promotion


@router.patch("/{id}", response_model=schemas.Promotion)
def update_promotion(
    *,
    db: Session = Depends(get_db),
    id: str,
    promotion_in: schemas.PromotionUpdate,
    current_user: User = Depends(require_superuser),
) -> Any:
    _require_promotion_admin(current_user)
    promotion = crud.promotion.get(db, id=id)
    if not promotion:
        raise HTTPException(status_code=404, detail="Promotion not found")
    try:
        return crud.promotion.update(db, db_obj=promotion, obj_in=promotion_in)
    except PromotionValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.to_detail())


@router.delete("/{id}")
def delete_promotion(
    *,
    db: Session = Depends(get_db),
    id: str,
    current_user: User = Depends(require_superuser),
) -> Any:
    _require_promotion_admin(current_user)
    promotion = crud.promotion.get(db, id=id)
    if not promotion:
        raise HTTPException(status_code=404, detail="Promotion not found")
    crud.promotion.disable(db, promotion=promotion)
    return {"status": "disabled"}
