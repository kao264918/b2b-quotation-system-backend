from sqlalchemy.orm import Session
from datetime import datetime
import uuid
from typing import Optional, List
from app.crud.base import CRUDBase
from app.models.quote import Quote, QuoteItem
from app.models.audit_log import AuditLog
from app.schemas.quote import QuoteCreate, QuoteUpdate

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

class CRUDQuote(CRUDBase[Quote, QuoteCreate, QuoteUpdate]):
    def create(self, db: Session, *, obj_in: QuoteCreate) -> Quote:
        obj_data = obj_in.model_dump()
        items_data = obj_data.pop("items", [])
        
        # Auto-generate quote_number if not provided
        if "quote_number" not in obj_data or not obj_data.get("quote_number"):
            date_prefix = datetime.now().strftime("%y%m")
            seq = uuid.uuid4().hex[:4].upper()
            obj_data["quote_number"] = f"QUO-{date_prefix}-{seq}"
        
        db_obj = Quote(**obj_data)
        db.add(db_obj)
        db.flush()
        
        for item in items_data:
            db_item = QuoteItem(**item, quote_id=db_obj.id)
            db.add(db_item)
        
        # Create audit log
        self._create_audit_log(db, db_obj.id, "create", AUDIT_CATEGORIES["create"], {"version": 1})
            
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
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
                db_item = QuoteItem(**item_data, quote_id=quote.id)
                db.add(db_item)
            
            changes["items"] = "updated"
            
            # Create audit log for items update
            self._create_audit_log(db, quote.id, "update_items", AUDIT_CATEGORIES["update_items"], changes)
        elif changes:
            # Create audit log for non-item changes
            category = "update_tax" if "tax_total" in changes else "update_items"
            self._create_audit_log(db, quote.id, category, AUDIT_CATEGORIES.get(category, "更新"), changes)
        
        db.add(quote)
        db.commit()
        db.refresh(quote)
        return quote
    
    def get_audit_logs(self, db: Session, quote_id: str) -> List[AuditLog]:
        """Get all audit logs for a quote."""
        return db.query(AuditLog).filter(
            AuditLog.entity_type == "quote",
            AuditLog.entity_id == quote_id
        ).order_by(AuditLog.timestamp.desc()).all()
    
    def _create_audit_log(self, db: Session, quote_id: str, action: str, category: str, changes: dict = None):
        """Create an audit log entry."""
        audit = AuditLog(
            entity_type="quote",
            entity_id=quote_id,
            action=action,
            changes={"category": category, **(changes or {})}
        )
        db.add(audit)

quote = CRUDQuote(Quote)

