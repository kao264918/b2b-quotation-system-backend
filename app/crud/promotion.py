from datetime import datetime
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.promotion import Promotion
from app.schemas.promotion import PromotionCreate, PromotionUpdate


def generate_promotion_code(db: Session, now: Optional[datetime] = None) -> str:
    now = now or datetime.now()
    date_prefix = now.strftime("%y%m")
    prefix = f"PROMO-{date_prefix}-"
    existing_codes = db.query(Promotion.promotion_code).filter(Promotion.promotion_code.like(f"{prefix}%")).all()

    max_seq = 0
    for (code,) in existing_codes:
        if not code:
            continue
        suffix = code.split("-")[-1]
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))
    return f"{prefix}{max_seq + 1:03d}"


class CRUDPromotion(CRUDBase[Promotion, PromotionCreate, PromotionUpdate]):
    def create(self, db: Session, *, obj_in: PromotionCreate) -> Promotion:
        obj_data = obj_in.model_dump()
        obj_data["promotion_code"] = generate_promotion_code(db)
        db_obj = Promotion(**obj_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_multi_filtered(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
    ):
        query = db.query(Promotion)
        if search:
            like = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Promotion.promotion_name.ilike(like),
                    Promotion.promotion_code.ilike(like),
                )
            )
        return query.order_by(Promotion.created_at.desc()).offset(skip).limit(limit).all()

    def disable(self, db: Session, *, promotion: Promotion) -> Promotion:
        promotion.is_active = False
        db.add(promotion)
        db.commit()
        db.refresh(promotion)
        return promotion


promotion = CRUDPromotion(Promotion)
