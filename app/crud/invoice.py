from sqlalchemy.orm import Session
from datetime import datetime
import uuid
from typing import Optional
from app.crud.base import CRUDBase
from app.models.invoice import Invoice, InvoiceItem
from app.models.quote import Quote
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate


def generate_invoice_number() -> str:
    """Generate unique invoice number: INV-YYMM-XXXX"""
    date_prefix = datetime.now().strftime("%y%m")
    seq = uuid.uuid4().hex[:4].upper()
    return f"INV-{date_prefix}-{seq}"


class CRUDInvoice(CRUDBase[Invoice, InvoiceCreate, InvoiceUpdate]):
    
    def get_multi(self, db: Session, *, skip: int = 0, limit: int = 100, include_deleted: bool = False):
        """Get multiple invoices, excluding soft-deleted by default."""
        query = db.query(Invoice)
        if not include_deleted:
            query = query.filter(Invoice.deleted_at.is_(None))
        return query.order_by(Invoice.created_at.desc()).offset(skip).limit(limit).all()
    
    def get(self, db: Session, id: str, include_deleted: bool = False) -> Optional[Invoice]:
        """Get invoice by ID, excluding soft-deleted by default."""
        query = db.query(Invoice).filter(Invoice.id == id)
        if not include_deleted:
            query = query.filter(Invoice.deleted_at.is_(None))
        return query.first()
    
    def create(self, db: Session, *, obj_in: InvoiceCreate) -> Invoice:
        obj_data = obj_in.model_dump()
        items_data = obj_data.pop("items", [])
        
        # Auto-generate invoice number if not provided
        if not obj_data.get("invoice_number"):
            obj_data["invoice_number"] = generate_invoice_number()
        
        db_obj = Invoice(**obj_data)
        db.add(db_obj)
        db.flush()
        
        for item in items_data:
            db_item = InvoiceItem(**item, invoice_id=db_obj.id)
            db.add(db_item)
            
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def create_from_quote(self, db: Session, *, quote: Quote) -> Invoice:
        """
        Create invoice from a confirmed quote.
        Snapshots all quote data into the invoice.
        """
        if quote.status != "confirmed":
            raise ValueError("只有已確認的報價單可以建立請款單")
        
        # Generate invoice number
        invoice_number = generate_invoice_number()
        
        # Create invoice with snapshot data
        invoice = Invoice(
            invoice_number=invoice_number,
            quote_id=quote.id,
            customer_id=quote.customer_id,
            status="draft",
            accounting_status="unpaid",
            subtotal=quote.subtotal,
            tax_total=quote.tax_total,
            total=quote.total,
            notes=quote.notes,
        )
        db.add(invoice)
        db.flush()
        
        # Snapshot items
        for item in quote.items:
            invoice_item = InvoiceItem(
                invoice_id=invoice.id,
                quote_item_id=item.id,
                name=item.name,
                description=item.description,
                quantity=item.quantity,
                unit=item.unit,
                unit_price=item.unit_price,
                tax_category_name=item.tax_category_name,
                tax_rate=item.tax_rate,
                subtotal=item.subtotal,
                tax_amount=item.tax_amount,
                total_amount=item.total_amount,
                line_total=item.line_total,
            )
            db.add(invoice_item)
        
        db.commit()
        db.refresh(invoice)
        return invoice
    
    def update_status(self, db: Session, *, invoice: Invoice, new_status: str) -> Invoice:
        """Update invoice status (draft → issued)."""
        valid_transitions = {
            "draft": ["issued"],
            "issued": ["paid", "void"],
            "paid": [],
            "void": [],
        }
        
        if new_status not in valid_transitions.get(invoice.status, []):
            raise ValueError(f"無效的狀態轉換：{invoice.status} → {new_status}")
        
        invoice.status = new_status
        
        if new_status == "issued" and not invoice.issued_at:
            invoice.issued_at = datetime.now()
        elif new_status == "paid" and not invoice.paid_at:
            invoice.paid_at = datetime.now()
        
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice
    
    def update_accounting_status(self, db: Session, *, invoice: Invoice, new_status: str) -> Invoice:
        """Update accounting status (unpaid/paid)."""
        if new_status not in ["unpaid", "paid"]:
            raise ValueError(f"無效的會計狀態：{new_status}")
        
        invoice.accounting_status = new_status
        if new_status == "paid" and not invoice.paid_at:
            invoice.paid_at = datetime.now()
        
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice
    
    def soft_delete(self, db: Session, *, invoice: Invoice) -> Invoice:
        """Soft delete an invoice."""
        invoice.deleted_at = datetime.now()
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice


invoice = CRUDInvoice(Invoice)
