from typing import List
from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerUpdate


class CRUDCustomer(CRUDBase[Customer, CustomerCreate, CustomerUpdate]):
    """CRUD operations for Customer with spec-compliant behaviors"""

    def get_multi_by_role(
        self, db: Session, *, role: str, status: str = "active", skip: int = 0, limit: int = 100
    ) -> List[Customer]:
        """Get customers filtered by role and status"""
        # Using simple string contains for JSON list since it's exact match string in list
        # For Postgres JSONB: .filter(self.model.roles.contains([role]))
        # For SQLite (dev): might need custom handling if JSON not fully supported, but SQLAlchemy usually handles it.
        # Assuming Postgres for prod, but local might be SQLite?
        # Let's try flexible approach or standard contains.
        return (
            db.query(self.model)
            .filter(self.model.status == status)
            .filter(func.json_each(self.model.roles).value == role)  # This works for SQLite JSON1
            # .filter(self.model.roles.contains([role])) # This is for Postgres JSONB
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_by_role(self, db: Session, *, role: str, status: str = "active") -> int:
        """Count customers filtered by role and status"""
        return (
            db.query(self.model)
            .filter(self.model.status == status)
            .filter(func.json_each(self.model.roles).value == role)
            .count()
        )

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

    def count_active(self, db: Session) -> int:
        """Count active customers for pagination"""
        return db.query(self.model).filter(self.model.status == "active").count()

    def get_multi_inactive(
        self, db: Session, skip: int = 0, limit: int = 100
    ) -> List[Customer]:
        """Get only inactive customers"""
        return (
            db.query(self.model)
            .filter(self.model.status == "inactive")
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_inactive(self, db: Session) -> int:
        """Count inactive customers for pagination"""
        return db.query(self.model).filter(self.model.status == "inactive").count()

    def get_by_company_name(self, db: Session, *, company_name: str) -> Customer | None:
        """Get customer by company_name for duplicate checking"""
        return db.query(self.model).filter(self.model.company_name == company_name).first()

    def soft_delete(self, db: Session, *, id: str) -> Customer:
        """Soft delete: set status to 'deleted' (invisible in frontend)"""
        obj = db.query(self.model).filter(self.model.id == id).first()
        if obj:
            obj.status = "deleted"
            db.add(obj)
            db.commit()
            db.refresh(obj)
        return obj


customer = CRUDCustomer(Customer)
