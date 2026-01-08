from typing import List, Any
from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models.customer import Customer, CustomerContact
from app.schemas.customer import CustomerCreate, CustomerUpdate

class CRUDCustomer(CRUDBase[Customer, CustomerCreate, CustomerUpdate]):
    def create(self, db: Session, *, obj_in: CustomerCreate) -> Customer:
        # Separate contacts from customer data
        obj_data = obj_in.model_dump()
        contacts_data = obj_data.pop("contacts", [])
        
        db_obj = Customer(**obj_data)
        db.add(db_obj)
        db.flush() # Generate ID for customer
        
        for contact in contacts_data:
            db_contact = CustomerContact(
                **contact,
                customer_id=db_obj.id
            )
            db.add(db_contact)
            
        db.commit()
        db.refresh(db_obj)
        return db_obj

customer = CRUDCustomer(Customer)
