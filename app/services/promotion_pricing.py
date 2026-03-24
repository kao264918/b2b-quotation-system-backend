from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.models.catalog import CatalogItem
from app.models.promotion import Promotion

ZERO = Decimal("0.00")
TWO_DP = Decimal("0.01")


class PromotionValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def to_detail(self) -> dict:
        return {"code": self.code, "message": self.message}


def quantize_money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(value).quantize(TWO_DP, rounding=ROUND_HALF_UP)


def get_promotion_runtime_status(promotion: Promotion, now: Optional[datetime] = None) -> str:
    now = now or datetime.now(timezone.utc)
    start_at = promotion.start_at if promotion.start_at.tzinfo else promotion.start_at.replace(tzinfo=timezone.utc)
    end_at = promotion.end_at if promotion.end_at.tzinfo else promotion.end_at.replace(tzinfo=timezone.utc)
    if not promotion.is_active:
        return "disabled"
    if now < start_at:
        return "scheduled"
    if now > end_at:
        return "expired"
    return "active"


def calculate_promotion_discount(subtotal: Decimal, promotion_type: str, discount_value: Decimal) -> Decimal:
    subtotal = quantize_money(subtotal)
    discount_value = quantize_money(discount_value)
    if subtotal <= ZERO:
        return ZERO
    if promotion_type == "percentage":
        return quantize_money(subtotal * discount_value / Decimal("100"))
    if promotion_type == "fixed_amount":
        return min(discount_value, subtotal)
    raise PromotionValidationError("PROMOTION_TYPE_UNSUPPORTED", "Promotion type is unsupported in v1.")


def _normalize_quote_item_category_values(
    db: Session,
    quote_items: Iterable[object],
) -> set[str]:
    category_values: set[str] = set()
    for item in quote_items:
        catalog_item_id = getattr(item, "catalog_item_id", None)
        if not catalog_item_id:
            continue
        catalog_item = (
            db.query(CatalogItem)
            .filter(CatalogItem.id == catalog_item_id, CatalogItem.deleted_at.is_(None))
            .first()
        )
        if catalog_item and catalog_item.category:
            category_values.add(str(catalog_item.category).strip().lower())
    return category_values


def quote_matches_promotion_scope(db: Session, quote_items: Iterable[object], promotion: Promotion) -> bool:
    if promotion.scope == "all_products":
        return True
    if promotion.scope != "category":
        return False
    if not promotion.scope_category:
        return False
    return promotion.scope_category.strip().lower() in _normalize_quote_item_category_values(db, quote_items)


def validate_promotion_for_quote(
    db: Session,
    promotion: Promotion,
    quote_items: Iterable[object],
    subtotal: Decimal,
    now: Optional[datetime] = None,
) -> Promotion:
    status = get_promotion_runtime_status(promotion, now=now)
    if status == "disabled":
        raise PromotionValidationError("PROMOTION_DISABLED", "Promotion is disabled.")
    if status == "scheduled":
        raise PromotionValidationError("PROMOTION_NOT_STARTED", "Promotion has not started yet.")
    if status == "expired":
        raise PromotionValidationError("PROMOTION_EXPIRED", "Promotion has already expired.")
    subtotal = quantize_money(subtotal)
    if subtotal < quantize_money(promotion.minimum_order_amount):
        raise PromotionValidationError("PROMOTION_MIN_ORDER_NOT_MET", "Promotion minimum order amount is not met.")
    if not quote_matches_promotion_scope(db, quote_items, promotion):
        raise PromotionValidationError("PROMOTION_SCOPE_NOT_MATCHED", "Promotion scope does not match quote items.")
    return promotion


def get_quote_tax_rate_from_setting(tax_setting: str) -> Decimal:
    mapping = {
        "taxable_5": Decimal("0.05"),
        "taxable_10": Decimal("0.10"),
        "non_taxable": Decimal("0.00"),
        "tax_exempt": Decimal("0.00"),
    }
    return mapping.get(tax_setting or "taxable_5", Decimal("0.05"))


def recalculate_quote_amounts_with_promotion(
    subtotal: Decimal,
    tax_setting: str,
    promotion: Promotion | None,
) -> dict:
    normalized_subtotal = quantize_money(subtotal)
    promotion_discount = ZERO
    if promotion is not None:
        promotion_discount = calculate_promotion_discount(
            normalized_subtotal,
            promotion.type,
            Decimal(promotion.discount_value),
        )
    before_tax = max(ZERO, quantize_money(normalized_subtotal - promotion_discount))
    tax_total = quantize_money(before_tax * get_quote_tax_rate_from_setting(tax_setting))
    total = quantize_money(before_tax + tax_total)
    return {
        "subtotal": normalized_subtotal,
        "promotion_discount_amount": promotion_discount,
        "tax_total": tax_total,
        "total": total,
        "before_tax": before_tax,
    }
