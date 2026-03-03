from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, List, Literal, Optional

from sqlalchemy import asc, case, desc, func
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.catalog import CatalogItem
from app.models.quote import Quote, QuoteItem
from app.models.audit_log import AuditLog
from app.schemas.quote import QuoteCreate, QuoteUpdate
from app.services.quote_costs import identify_missing_cost_item_ids, recalculate_quote_cost_fields

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


class CRUDQuote(CRUDBase[Quote, QuoteCreate, QuoteUpdate]):
    SORTABLE_FIELDS = {
        "created_at": Quote.created_at,
        "subtotal": Quote.subtotal,
        "total_cost": Quote.total_cost,
        "gross_profit_amount": Quote.gross_profit_amount,
        "gross_profit_rate": Quote.gross_profit_rate,
    }

    def create(self, db: Session, *, obj_in: QuoteCreate) -> Quote:
        obj_data = obj_in.model_dump()
        items_data = obj_data.pop("items", [])
        
        # Auto-generate quote_number with monthly sequence
        if "quote_number" not in obj_data or not obj_data.get("quote_number"):
            date_prefix = datetime.now().strftime("%y%m")
            prefix = f"QUO-{date_prefix}-"
            
            # Query all existing quote numbers for this month to find the next sequence
            # This is safer than max() because of mixed legacy ID formats (e.g. hex suffixes)
            existing_numbers = db.query(Quote.quote_number).filter(
                Quote.quote_number.like(f"{prefix}%")
            ).all()
            
            max_seq = 0
            for (q_num,) in existing_numbers:
                if not q_num: continue
                try:
                    # Extract suffix after last hyphen
                    parts = q_num.split("-")
                    if len(parts) >= 3:
                        suffix = parts[-1]
                        # Only consider numeric suffixes to avoid legacy hex IDs
                        if suffix.isdigit():
                            seq = int(suffix)
                            if seq > max_seq:
                                max_seq = seq
                except (ValueError, IndexError):
                    continue
            
            next_seq = max_seq + 1
            obj_data["quote_number"] = f"{prefix}{next_seq:03d}"
        
        db_obj = Quote(**obj_data)
        db.add(db_obj)
        db.flush()
        
        for item in items_data:
            db_item = QuoteItem(**self._prepare_item_data(db, item), quote_id=db_obj.id)
            db.add(db_item)

        db.flush()
        db.refresh(db_obj)
        recalculate_quote_cost_fields(db_obj)
        
        # Create audit log
        self._create_audit_log(db, db_obj.id, "create", AUDIT_CATEGORIES["create"], {"version": 1})
            
        db.commit()
        db.refresh(db_obj)
        return db_obj

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
    
    def update_status(self, db: Session, *, quote: Quote, new_status: str) -> Quote:
        """Update quotation status with transition validation."""
        current_status = quote.status
        
        if new_status not in VALID_TRANSITIONS.get(current_status, []):
            raise ValueError(f"Invalid status transition: {current_status} → {new_status}")
        
        old_status = quote.status
        quote.status = new_status
        
        # Set accounting_status to unpaid when transitioning to confirmed
        if new_status == "confirmed" and quote.accounting_status is None:
            quote.accounting_status = "unpaid"
        if new_status == "confirmed":
            recalculate_quote_cost_fields(quote)
            missing_item_ids = identify_missing_cost_item_ids(quote.items)
            if missing_item_ids:
                raise QuoteValidationError(
                    "QUOTATION_COST_INCOMPLETE",
                    "Quotation contains items without cost snapshot.",
                    {"missing_item_ids": missing_item_ids},
                )
            quote.confirmed_at = datetime.now(timezone.utc)
        
        # Create audit log
        self._create_audit_log(db, quote.id, "status_change", AUDIT_CATEGORIES["status_change"], {
            "from": old_status,
            "to": new_status
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
            self._create_audit_log(db, quote.id, category, AUDIT_CATEGORIES.get(category, "更新"), changes)
        
        db.flush()
        db.refresh(quote)
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
                "Quote items must be selected from catalog.",
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

quote = CRUDQuote(Quote)
