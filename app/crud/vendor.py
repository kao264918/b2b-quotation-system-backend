from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models.vendor import Vendor, VendorContact
from app.schemas.vendor import VendorCreate, VendorUpdate

class CRUDVendor(CRUDBase[Vendor, VendorCreate, VendorUpdate]):
    def create(self, db: Session, *, obj_in: VendorCreate) -> Vendor:
        obj_data = obj_in.model_dump()
        contacts_data = obj_data.pop("contacts", [])
        
        db_obj = Vendor(**obj_data)
        db.add(db_obj)
        db.flush()
        
        for contact in contacts_data:
            db_contact = VendorContact(
                **contact,
                vendor_id=db_obj.id
            )
            db.add(db_contact)
            
        db.commit()
        db.refresh(db_obj)
        return db_obj

vendor = CRUDVendor(Vendor)
