from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, cast
from sqlalchemy.dialects.postgresql import JSONB
from app.crud.base import CRUDBase
from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerUpdate


class CRUDCustomer(CRUDBase[Customer, CustomerCreate, CustomerUpdate]):
    """CRUD operations for Customer with spec-compliant behaviors"""

    def get_multi_by_role(
        self, db: Session, *, role: str, status: str = "active", search: str = None, skip: int = 0, limit: int = 100
    ) -> List[Customer]:
        """Get customers filtered by role and status, optionally search by name/tax_id"""
        query = db.query(self.model).filter(self.model.status == status)
        
        # Role filter - use contains for JSON array (Postgres @> operator)
        # Note: Postgres 'json' type doesn't support @>, so we cast to JSONB
        query = query.filter(cast(self.model.roles, JSONB).contains([role]))
        
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    self.model.company_name.ilike(search_pattern),
                    self.model.tax_id.ilike(search_pattern),
                    self.model.contact_name.ilike(search_pattern),
                    self.model.contact_email.ilike(search_pattern),
                )
            )
            
        return query.offset(skip).limit(limit).all()

    def count_by_role(self, db: Session, *, role: str, status: str = "active", search: str = None) -> int:
        """Count customers filtered by role and status"""
        query = db.query(self.model).filter(self.model.status == status)
        query = query.filter(cast(self.model.roles, JSONB).contains([role]))
        
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    self.model.company_name.ilike(search_pattern),
                    self.model.tax_id.ilike(search_pattern),
                    self.model.contact_name.ilike(search_pattern),
                    self.model.contact_email.ilike(search_pattern),
                )
            )
            
        return query.count()

    def get_multi_active(
        self, db: Session, search: str = None, skip: int = 0, limit: int = 100
    ) -> List[Customer]:
        """Get only active customers (default list behavior per spec)"""
        query = db.query(self.model).filter(self.model.status == "active")
        
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    self.model.company_name.ilike(search_pattern),
                    self.model.tax_id.ilike(search_pattern),
                    self.model.contact_name.ilike(search_pattern),
                    self.model.contact_email.ilike(search_pattern),
                )
            )
            
        return query.offset(skip).limit(limit).all()

    def count_active(self, db: Session, search: str = None) -> int:
        """Count active customers for pagination"""
        query = db.query(self.model).filter(self.model.status == "active")
        
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    self.model.company_name.ilike(search_pattern),
                    self.model.tax_id.ilike(search_pattern),
                    self.model.contact_name.ilike(search_pattern),
                    self.model.contact_email.ilike(search_pattern),
                )
            )
            
        return query.count()

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
