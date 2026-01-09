from typing import List
from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerUpdate


class CRUDCustomer(CRUDBase[Customer, CustomerCreate, CustomerUpdate]):
    """CRUD operations for Customer with spec-compliant behaviors"""

    def get_multi_active(
        self, db: Session, skip: int = 0, limit: int = 100
    ) -> List[Customer]:
        """Get only active customers (default list behavior per spec)"""
        return (
            db.query(self.model)
            .filter(self.model.status == "active")
            .offset(skip)
            .limit(limit)
            .all()
        )

    def soft_delete(self, db: Session, *, id: str) -> Customer:
        """Soft delete: set status to inactive instead of hard delete"""
        obj = db.query(self.model).filter(self.model.id == id).first()
        if obj:
            obj.status = "inactive"
            db.add(obj)
            db.commit()
            db.refresh(obj)
        return obj


customer = CRUDCustomer(Customer)
