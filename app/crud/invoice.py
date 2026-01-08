from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models.invoice import Invoice, InvoiceItem
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate

class CRUDInvoice(CRUDBase[Invoice, InvoiceCreate, InvoiceUpdate]):
    def create(self, db: Session, *, obj_in: InvoiceCreate) -> Invoice:
        obj_data = obj_in.model_dump()
        items_data = obj_data.pop("items", [])
        
        db_obj = Invoice(**obj_data)
        db.add(db_obj)
        db.flush()
        
        for item in items_data:
            db_item = InvoiceItem(**item, invoice_id=db_obj.id)
            db.add(db_item)
            
        db.commit()
        db.refresh(db_obj)
        return db_obj

invoice = CRUDInvoice(Invoice)
