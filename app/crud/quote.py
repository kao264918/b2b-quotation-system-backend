from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, List, Literal, Optional

from sqlalchemy import asc, case, desc, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, load_only, noload

from app.crud.base import CRUDBase
from app.models.catalog import CatalogItem
from app.models.customer import Customer
from app.models.promotion import Promotion
from app.models.quote import Quote, QuoteItem
from app.models.audit_log import AuditLog
from app.schemas.quote import QuoteCreate, QuoteUpdate
from app.services.quote_costs import identify_missing_cost_item_ids, recalculate_quote_cost_fields
from app.services.promotion_pricing import (
    PromotionValidationError,
    recalculate_quote_amounts_with_promotion,
    validate_promotion_for_quote,
)

# Valid status transitions
VALID_TRANSITIONS = {
    "draft": ["confirmed"],
    "confirmed": ["closed", "discarded"],
    "closed": [],  # Requires revert
    "discarded": [],  # Requires revert
}

# Audit categories (Chinese)
AUDIT_CATEGORIES = {
    "create": "建立報價單",
    "update_items": "更新項目內容",
    "update_tax": "更新稅務設定",
    "update_promotion": "更新促銷活動",
    "status_change": "狀態變更",
    "accounting_status_change": "會計狀態變更",
    "revert": "重啟報價",
}


class QuoteValidationError(ValueError):
    def __init__(self, code: str, message: str, extra: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.extra = extra or {}

    def to_detail(self) -> dict:
        return {"code": self.code, "message": self.message, **self.extra}


def _is_quote_valid_until_expired(quote: Quote) -> bool:
    if not quote.valid_until:
        return False
    valid_until = quote.valid_until
    if valid_until.tzinfo is None:
        valid_until = valid_until.replace(tzinfo=timezone.utc)
    return valid_until < datetime.now(timezone.utc)


def _promotion_snapshot_payload(quote: Quote) -> dict | None:
    if not quote.promotion_id:
        return None
    return {
        "promotion_id": quote.promotion_id,
        "promotion_name": quote.promotion_name_snapshot or getattr(quote.promotion, "promotion_name", None),
        "promotion_type": quote.promotion_type_snapshot or getattr(quote.promotion, "type", None),
        "promotion_value": str(quote.promotion_value_snapshot or getattr(quote.promotion, "discount_value", "0.00")),
        "promotion_discount_amount": str(quote.promotion_discount_amount),
    }


class CRUDQuote(CRUDBase[Quote, QuoteCreate, QuoteUpdate]):
    SORTABLE_FIELDS = {
        "created_at": Quote.created_at,
        "subtotal": Quote.subtotal,
        "total_cost": Quote.total_cost,
        "gross_profit_amount": Quote.gross_profit_amount,
        "gross_profit_rate": Quote.gross_profit_rate,
    }
    LIST_LOAD_COLUMNS = (
        Quote.id,
        Quote.quote_number,
        Quote.customer_id,
        Quote.title,
        Quote.status,
        Quote.accounting_status,
        Quote.version,
        Quote.subtotal,
        Quote.promotion_discount_amount,
        Quote.tax_total,
        Quote.total,
        Quote.cost_status,
        Quote.total_cost,
        Quote.gross_profit_amount,
        Quote.gross_profit_rate,
        Quote.valid_until,
        Quote.created_at,
        Quote.updated_at,
    )

    def _generate_quote_number(self, db: Session) -> str:
        date_prefix = datetime.now().strftime("%y%m")
        prefix = f"QUO-{date_prefix}-"

        existing_numbers = db.query(Quote.quote_number).filter(
            Quote.quote_number.like(f"{prefix}%")
        ).all()

        max_seq = 0
        for (q_num,) in existing_numbers:
            if not q_num:
                continue
            try:
                parts = q_num.split("-")
                if len(parts) >= 3:
                    suffix = parts[-1]
                    if suffix.isdigit():
                        seq = int(suffix)
                        if seq > max_seq:
                            max_seq = seq
            except (ValueError, IndexError):
                continue

        return f"{prefix}{max_seq + 1:03d}"

    def _is_duplicate_quote_number_error(self, exc: IntegrityError) -> bool:
        message = str(getattr(exc, "orig", exc)).lower()
        return "quote_number" in message

    def _build_quote(self, db: Session, *, obj_data: dict, items_data: list[dict]) -> Quote:
        db_obj = Quote(**obj_data)
        db.add(db_obj)
        db.flush()

        for item in items_data:
            db_item = QuoteItem(**self._prepare_item_data(db, item), quote_id=db_obj.id)
            db.add(db_item)

        db.flush()
        db.refresh(db_obj)
        self._apply_promotion_to_quote(db, quote=db_obj, promotion_id=obj_data.get("promotion_id"))
        recalculate_quote_cost_fields(db_obj)
        self._create_audit_log(
            db,
            db_obj.id,
            "create",
            AUDIT_CATEGORIES["create"],
            {"version": 1, "promotion": _promotion_snapshot_payload(db_obj)},
        )
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def create(self, db: Session, *, obj_in: QuoteCreate) -> Quote:
        base_data = obj_in.model_dump()
        items_data = base_data.pop("items", [])

        for _ in range(5):
            obj_data = dict(base_data)
            if "quote_number" not in obj_data or not obj_data.get("quote_number"):
                obj_data["quote_number"] = self._generate_quote_number(db)
            try:
                return self._build_quote(db, obj_data=obj_data, items_data=items_data)
            except IntegrityError as exc:
                db.rollback()
                if not self._is_duplicate_quote_number_error(exc):
                    raise
        raise ValueError("Failed to generate unique quote number after multiple attempts.")

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        sort_by: Optional[str] = None,
        sort_order: Literal["asc", "desc"] = "desc",
    ) -> List[Quote]:
        query = db.query(self.model)
        sort_key = sort_by if sort_by in self.SORTABLE_FIELDS else "created_at"
        sort_column = self.SORTABLE_FIELDS[sort_key]
        order_fn = asc if sort_order == "asc" else desc

        if sort_key in {"total_cost", "gross_profit_amount", "gross_profit_rate"}:
            query = query.order_by(
                case((Quote.cost_status == "missing", 1), else_=0).asc(),
                order_fn(sort_column),
            )
        else:
            query = query.order_by(order_fn(sort_column))

        return query.offset(skip).limit(limit).all()

    def count_multi(self, db: Session) -> int:
        return db.query(func.count(self.model.id)).scalar() or 0

    def _apply_list_filters(self, query, search: Optional[str] = None):
        if search:
            search_term = f"%{search.strip()}%"
            if search_term != "%%":
                query = query.filter(
                    or_(
                        Quote.quote_number.ilike(search_term),
                        Quote.title.ilike(search_term),
                        Customer.company_name.ilike(search_term),
                    )
                )
        return query

    def get_list_page(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: Literal["asc", "desc"] = "desc",
    ) -> List[Quote]:
        query = (
            db.query(self.model)
            .join(Customer, Quote.customer_id == Customer.id)
            .options(
                load_only(*self.LIST_LOAD_COLUMNS),
                joinedload(Quote.customer).load_only(
                    Customer.id,
                    Customer.company_name,
                    Customer.tax_id,
                    Customer.company_email,
                    Customer.contact_name,
                    Customer.contact_phone,
                    Customer.contact_email,
                ),
                noload(Quote.items),
                noload(Quote.promotion),
                noload(Quote.rfq),
            )
        )
        query = self._apply_list_filters(query, search)

        sort_key = sort_by if sort_by in self.SORTABLE_FIELDS else "created_at"
        sort_column = self.SORTABLE_FIELDS[sort_key]
        order_fn = asc if sort_order == "asc" else desc

        if sort_key in {"total_cost", "gross_profit_amount", "gross_profit_rate"}:
            query = query.order_by(
                case((Quote.cost_status == "missing", 1), else_=0).asc(),
                order_fn(sort_column),
            )
        else:
            query = query.order_by(order_fn(sort_column))

        return query.offset(skip).limit(limit).all()

    def count_list(self, db: Session, *, search: Optional[str] = None) -> int:
        query = db.query(func.count(self.model.id)).join(Customer, Quote.customer_id == Customer.id)
        query = self._apply_list_filters(query, search)
        return query.scalar() or 0
    
    def update_status(self, db: Session, *, quote: Quote, new_status: str) -> Quote:
        """Update quotation status with transition validation."""
        current_status = quote.status
        
        if new_status not in VALID_TRANSITIONS.get(current_status, []):
            raise ValueError(f"Invalid status transition: {current_status} → {new_status}")
        if new_status == "confirmed" and _is_quote_valid_until_expired(quote):
            raise QuoteValidationError(
                "QUOTATION_EXPIRED",
                "Quotation valid until date has already passed.",
            )
        
        old_status = quote.status
        quote.status = new_status
        
        # Set accounting_status to unpaid when transitioning to confirmed
        if new_status == "confirmed" and quote.accounting_status is None:
            quote.accounting_status = "unpaid"
        if new_status == "confirmed":
            self._apply_promotion_to_quote(db, quote=quote, promotion_id=quote.promotion_id)
            recalculate_quote_cost_fields(quote)
            missing_item_ids = identify_missing_cost_item_ids(quote.items)
            if missing_item_ids:
                raise QuoteValidationError(
                    "QUOTATION_COST_INCOMPLETE",
                    "Quotation contains items without cost snapshot.",
                    {"missing_item_ids": missing_item_ids},
                )
            self._snapshot_promotion(quote)
            quote.confirmed_at = datetime.now(timezone.utc)
        
        # Create audit log
        self._create_audit_log(db, quote.id, "status_change", AUDIT_CATEGORIES["status_change"], {
            "from": old_status,
            "to": new_status,
            "promotion": _promotion_snapshot_payload(quote),
        })
        
        db.add(quote)
        db.commit()
        db.refresh(quote)
        return quote
    
    def update_accounting_status(self, db: Session, *, quote: Quote, new_status: str) -> Quote:
        """Update accounting status (only allowed for confirmed/closed/discarded)."""
        if quote.status == "draft":
            raise ValueError("Cannot update accounting status for draft quotes")
        
        if new_status not in ["unpaid", "paid"]:
            raise ValueError(f"Invalid accounting status: {new_status}")
        
        old_status = quote.accounting_status
        quote.accounting_status = new_status
        
        # Create audit log
        self._create_audit_log(db, quote.id, "accounting_status_change", AUDIT_CATEGORIES["accounting_status_change"], {
            "from": old_status,
            "to": new_status
        })
        
        db.add(quote)
        db.commit()
        db.refresh(quote)
        return quote
    
    def revert_quote(self, db: Session, *, quote: Quote) -> Quote:
        """Revert a confirmed/closed/discarded quote back to draft, creating a new version."""
        if quote.status not in ["confirmed", "closed", "discarded"]:
            raise ValueError("只有已建立、結案或作廢的報價單可以重啟")
        
        old_status = quote.status
        old_version = quote.version
        
        # Increment version and set status to draft for editing
        quote.version = old_version + 1
        quote.status = "draft"
        quote.accounting_status = None  # Draft quotes have no accounting status
        quote.confirmed_at = None
        quote.promotion_code_snapshot = None
        quote.promotion_name_snapshot = None
        quote.promotion_type_snapshot = None
        quote.promotion_value_snapshot = None
        quote.promotion_scope_snapshot = None
        quote.promotion_scope_category_snapshot = None
        try:
            self._apply_promotion_to_quote(db, quote=quote, promotion_id=quote.promotion_id)
        except QuoteValidationError as exc:
            if not exc.code.startswith("PROMOTION_"):
                raise
            quote.subtotal = sum((Decimal(item.subtotal) for item in quote.items), Decimal("0.00"))
            amounts = recalculate_quote_amounts_with_promotion(
                Decimal(quote.subtotal),
                quote.tax_setting,
                None,
            )
            quote.promotion_discount_amount = amounts["promotion_discount_amount"]
            quote.tax_total = amounts["tax_total"]
            quote.total = amounts["total"]
        recalculate_quote_cost_fields(quote)
        
        # Create audit log
        self._create_audit_log(db, quote.id, "revert", AUDIT_CATEGORIES["revert"], {
            "from_status": old_status,
            "from_version": old_version,
            "to_version": quote.version,
            "to_status": "draft"
        })
        
        db.add(quote)
        db.commit()
        db.refresh(quote)
        return quote
    
    def update_with_items(self, db: Session, *, quote: Quote, obj_in: QuoteUpdate) -> Quote:
        """Update quote with items, creating new version if items changed."""
        obj_data = obj_in.model_dump(exclude_unset=True)
        items_data = obj_data.pop("items", None)
        
        # Check if quote is editable
        if quote.status != "draft":
            raise ValueError("Only draft quotes can be edited directly. Use revert first.")
        
        # Track changes for audit
        changes = {}
        
        # Update basic fields
        for field, value in obj_data.items():
            if hasattr(quote, field) and getattr(quote, field) != value:
                changes[field] = {"from": getattr(quote, field), "to": value}
                setattr(quote, field, value)
        
        # Update items if provided
        if items_data is not None:
            # Delete existing items
            for item in quote.items:
                db.delete(item)
            
            # Create new items
            for item_data in items_data:
                db_item = QuoteItem(**self._prepare_item_data(db, item_data), quote_id=quote.id)
                db.add(db_item)
            
            changes["items"] = "updated"
            
            # Create audit log for items update
            self._create_audit_log(db, quote.id, "update_items", AUDIT_CATEGORIES["update_items"], changes)
        elif changes:
            # Create audit log for non-item changes
            category = "update_tax" if "tax_total" in changes else "update_items"
            if "promotion_id" in changes:
                category = "update_promotion"
            self._create_audit_log(db, quote.id, category, AUDIT_CATEGORIES.get(category, "更新"), changes)
        
        db.flush()
        db.refresh(quote)
        self._apply_promotion_to_quote(db, quote=quote, promotion_id=obj_data.get("promotion_id", quote.promotion_id))
        recalculate_quote_cost_fields(quote)
        
        db.add(quote)
        db.commit()
        db.refresh(quote)
        return quote

    def get_internal_kpi(self, db: Session, *, range_type: Literal["month", "quarter", "all"]) -> dict:
        now = datetime.now(timezone.utc)
        start_at: Optional[datetime] = None
        if range_type == "month":
            start_at = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        elif range_type == "quarter":
            quarter_start_month = ((now.month - 1) // 3) * 3 + 1
            start_at = datetime(now.year, quarter_start_month, 1, tzinfo=timezone.utc)

        query = db.query(Quote).filter(Quote.status == "confirmed")
        if start_at is not None:
            query = query.filter(Quote.confirmed_at >= start_at, Quote.confirmed_at <= now)

        total_revenue = query.with_entities(func.coalesce(func.sum(Quote.subtotal), 0)).scalar() or Decimal("0")
        total_cost = query.with_entities(func.coalesce(func.sum(Quote.total_cost), 0)).scalar() or Decimal("0")
        avg_gp_rate = (
            query.filter(Quote.cost_status == "ok")
            .with_entities(func.coalesce(func.avg(Quote.gross_profit_rate), 0))
            .scalar()
            or Decimal("0")
        )
        count = query.count()

        return {
            "range": range_type,
            "count": count,
            "total_revenue_excl_tax": Decimal(total_revenue),
            "total_cost": Decimal(total_cost),
            "average_gross_profit_rate": Decimal(avg_gp_rate),
        }
    
    def get_audit_logs(self, db: Session, quote_id: str) -> List[AuditLog]:
        """Get all audit logs for a quote."""
        return db.query(AuditLog).filter(
            AuditLog.entity_type == "quote",
            AuditLog.entity_id == quote_id
        ).order_by(AuditLog.timestamp.desc()).all()
    
    def _create_audit_log(self, db: Session, quote_id: str, action: str, category: str, changes: dict = None):
        """Create an audit log entry."""
        # Sanitize changes (Decimal/datetime) for JSON serialization
        safe_changes = self._serialize_changes({"category": category, **(changes or {})})
        
        audit = AuditLog(
            entity_type="quote",
            entity_id=quote_id,
            action=action,
            changes=safe_changes
        )
        db.add(audit)

    def _serialize_changes(self, data: Any) -> Any:
        """Helper to serialize data for JSON storage (Decimal, datetime)"""
        if isinstance(data, dict):
            return {k: self._serialize_changes(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._serialize_changes(v) for v in data]
        elif isinstance(data, Decimal):
            return str(data) # or float(data)
        elif isinstance(data, (datetime, date)):
            return data.isoformat()
        return data

    def _prepare_item_data(self, db: Session, item_data: dict) -> dict:
        data = {**item_data}
        catalog_item_id = data.get("catalog_item_id")
        if not catalog_item_id:
            raise QuoteValidationError(
                "QUOTE_CUSTOM_ITEM_FORBIDDEN",
                "品項需先於品項管理建立後再加入報價。",
            )

        catalog_item = (
            db.query(CatalogItem)
            .filter(CatalogItem.id == catalog_item_id, CatalogItem.deleted_at.is_(None))
            .first()
        )
        if not catalog_item:
            raise QuoteValidationError("CATALOG_ITEM_NOT_FOUND", "Catalog item not found.")
        if catalog_item.reference_cost is None:
            raise QuoteValidationError("CATALOG_COST_MISSING", "Catalog item cost is missing.")

        data["snapshot_cost"] = Decimal(catalog_item.reference_cost)
        return data

    def _apply_promotion_to_quote(self, db: Session, *, quote: Quote, promotion_id: str | None) -> None:
        quote.subtotal = sum((Decimal(item.subtotal) for item in quote.items), Decimal("0.00"))
        promotion = None
        if promotion_id:
            promotion = db.query(Promotion).filter(Promotion.id == promotion_id).first()
            if not promotion:
                raise QuoteValidationError("PROMOTION_NOT_FOUND", "Promotion not found.")
            try:
                validate_promotion_for_quote(db, promotion, quote.items, Decimal(quote.subtotal))
            except PromotionValidationError as exc:
                raise QuoteValidationError(exc.code, exc.message)
        amounts = recalculate_quote_amounts_with_promotion(
            Decimal(quote.subtotal),
            quote.tax_setting,
            promotion,
        )
        quote.promotion_id = promotion.id if promotion else None
        quote.promotion_discount_amount = amounts["promotion_discount_amount"]
        quote.tax_total = amounts["tax_total"]
        quote.total = amounts["total"]

    def _snapshot_promotion(self, quote: Quote) -> None:
        if not quote.promotion:
            quote.promotion_code_snapshot = None
            quote.promotion_name_snapshot = None
            quote.promotion_type_snapshot = None
            quote.promotion_value_snapshot = None
            quote.promotion_scope_snapshot = None
            quote.promotion_scope_category_snapshot = None
            quote.promotion_discount_amount = Decimal(quote.promotion_discount_amount or 0)
            return

        quote.promotion_code_snapshot = quote.promotion.promotion_code
        quote.promotion_name_snapshot = quote.promotion.promotion_name
        quote.promotion_type_snapshot = quote.promotion.type
        quote.promotion_value_snapshot = Decimal(quote.promotion.discount_value)
        quote.promotion_scope_snapshot = quote.promotion.scope
        quote.promotion_scope_category_snapshot = quote.promotion.scope_category

quote = CRUDQuote(Quote)
