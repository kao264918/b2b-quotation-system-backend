from sqlalchemy import or_
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
from typing import Optional
from app.crud.base import CRUDBase
from app.models.invoice import Invoice, InvoiceItem
from app.models.customer import Customer
from app.models.quote import Quote
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate


def generate_invoice_number() -> str:
    """Generate unique invoice number: INV-YYMM-XXXX"""
    date_prefix = datetime.now().strftime("%y%m")
    seq = uuid.uuid4().hex[:4].upper()
    return f"INV-{date_prefix}-{seq}"


class CRUDInvoice(CRUDBase[Invoice, InvoiceCreate, InvoiceUpdate]):
    def get_by_quote(self, db: Session, *, quote_id: str, include_deleted: bool = False) -> Optional[Invoice]:
        query = db.query(Invoice).filter(Invoice.quote_id == quote_id)
        if not include_deleted:
            query = query.filter(Invoice.deleted_at.is_(None))
        return query.order_by(Invoice.created_at.desc()).first()
    
    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False,
        quote_id: str | None = None,
        search: str | None = None,
    ):
        """Get multiple invoices, excluding soft-deleted by default."""
        query = db.query(Invoice)
        if not include_deleted:
            query = query.filter(Invoice.deleted_at.is_(None))
        if quote_id:
            query = query.filter(Invoice.quote_id == quote_id)
        if search:
            term = f"%{search.strip()}%"
            query = (
                query.join(Invoice.customer)
                .join(Invoice.quote)
                .filter(
                    or_(
                        Invoice.invoice_number.ilike(term),
                        Customer.company_name.ilike(term),
                        Quote.quote_number.ilike(term),
                        Quote.title.ilike(term),
                    )
                )
            )
        total = query.count()
        items = query.order_by(Invoice.created_at.desc()).offset(skip).limit(limit).all()
        return items, total
    
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

        existing_invoice = self.get_by_quote(db, quote_id=quote.id)
        if existing_invoice:
            raise ValueError("此報價單已建立請款單")
        
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
            promotion_discount_amount=quote.promotion_discount_amount,
            promotion_code_snapshot=quote.promotion_code_snapshot,
            promotion_name_snapshot=quote.promotion_name_snapshot,
            promotion_type_snapshot=quote.promotion_type_snapshot,
            promotion_value_snapshot=quote.promotion_value_snapshot,
            promotion_scope_snapshot=quote.promotion_scope_snapshot,
            promotion_scope_category_snapshot=quote.promotion_scope_category_snapshot,
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
        """Update invoice status with unified lifecycle transitions."""
        valid_transitions = {
            "draft": ["issued", "void"],
            "issued": ["draft", "paid", "void"],
            "paid": ["issued"],
            "void": [],
        }
        
        if new_status not in valid_transitions.get(invoice.status, []):
            raise ValueError(f"無效的狀態轉換：{invoice.status} → {new_status}")
        
        invoice.status = new_status
        
        if new_status == "draft":
            invoice.accounting_status = "unpaid"
        elif new_status == "issued":
            if not invoice.issued_at:
                invoice.issued_at = datetime.now()
            invoice.accounting_status = "unpaid"
        elif new_status == "paid":
            if not invoice.issued_at:
                invoice.issued_at = datetime.now()
            if not invoice.paid_at:
                invoice.paid_at = datetime.now()
            invoice.accounting_status = "paid"
        
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice
    
    def update_accounting_status(self, db: Session, *, invoice: Invoice, new_status: str) -> Invoice:
        """Legacy compatibility: map accounting updates onto unified status."""
        if new_status not in ["unpaid", "paid"]:
            raise ValueError(f"無效的會計狀態：{new_status}")

        if new_status == "paid":
            if invoice.status == "paid":
                return invoice
            return self.update_status(db, invoice=invoice, new_status="paid")

        if invoice.status == "paid":
            return self.update_status(db, invoice=invoice, new_status="issued")

        raise ValueError("只有已付款的請款單可以撤銷付款")
    
    def soft_delete(self, db: Session, *, invoice: Invoice) -> Invoice:
        """Soft delete an invoice."""
        invoice.deleted_at = datetime.now()
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice


invoice = CRUDInvoice(Invoice)
