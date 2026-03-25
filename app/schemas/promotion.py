from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, computed_field, field_validator


PromotionType = Literal["percentage", "fixed_amount", "bundle"]
PromotionScope = Literal["all_products", "category"]
PromotionStatus = Literal["active", "scheduled", "expired", "disabled"]


class PromotionBase(BaseModel):
    promotion_name: str
    description: Optional[str] = None
    internal_memo: Optional[str] = None
    type: PromotionType
    discount_value: Decimal
    minimum_order_amount: Decimal = Decimal("0.00")
    scope: PromotionScope = "all_products"
    scope_category: Optional[str] = None
    start_at: datetime
    end_at: datetime
    is_active: bool = True

    @field_validator("discount_value")
    @classmethod
    def validate_discount_value(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("discount_value must be greater than 0")
        return value

    @field_validator("minimum_order_amount")
    @classmethod
    def validate_minimum_order_amount(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("minimum_order_amount must be greater than or equal to 0")
        return value

    @field_validator("end_at")
    @classmethod
    def validate_date_range(cls, value: datetime, values) -> datetime:
        start_at = values.data.get("start_at")
        if start_at and value < start_at:
            raise ValueError("end_at must be after or equal to start_at")
        return value

    @field_validator("type")
    @classmethod
    def reject_bundle(cls, value: PromotionType) -> PromotionType:
        if value == "bundle":
            raise ValueError("bundle promotions are reserved and unsupported in v1")
        return value

    @field_validator("scope_category")
    @classmethod
    def validate_scope_category(cls, value: Optional[str], values) -> Optional[str]:
        scope = values.data.get("scope")
        cleaned = value.strip() if isinstance(value, str) else value
        if scope == "category" and not cleaned:
            raise ValueError("scope_category is required when scope=category")
        if scope == "all_products":
            return None
        return cleaned


class PromotionCreate(PromotionBase):
    pass


class PromotionUpdate(BaseModel):
    promotion_name: Optional[str] = None
    description: Optional[str] = None
    internal_memo: Optional[str] = None
    type: Optional[PromotionType] = None
    discount_value: Optional[Decimal] = None
    minimum_order_amount: Optional[Decimal] = None
    scope: Optional[PromotionScope] = None
    scope_category: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    is_active: Optional[bool] = None

    @field_validator("type")
    @classmethod
    def reject_bundle(cls, value: Optional[PromotionType]) -> Optional[PromotionType]:
        if value == "bundle":
            raise ValueError("bundle promotions are reserved and unsupported in v1")
        return value


class Promotion(PromotionBase):
    id: str
    promotion_code: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def status(self) -> PromotionStatus:
        now = datetime.now(timezone.utc)
        start_at = self.start_at if self.start_at.tzinfo else self.start_at.replace(tzinfo=timezone.utc)
        end_at = self.end_at if self.end_at.tzinfo else self.end_at.replace(tzinfo=timezone.utc)
        if not self.is_active:
            return "disabled"
        if now < start_at:
            return "scheduled"
        if now > end_at:
            return "expired"
        return "active"


class PromotionSelectorItem(BaseModel):
    id: str
    promotion_code: str
    promotion_name: str
    type: Literal["percentage", "fixed_amount"]
    discount_value: Decimal
    minimum_order_amount: Decimal
    scope: PromotionScope
    scope_category: Optional[str] = None
    start_at: datetime
    end_at: datetime
    is_active: bool
    status: PromotionStatus

    model_config = ConfigDict(from_attributes=True)
