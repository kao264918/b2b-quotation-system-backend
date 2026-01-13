from typing import Optional, List
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.unit import Unit
from app.schemas.unit import UnitCreate, UnitUpdate


class CRUDUnit(CRUDBase[Unit, UnitCreate, UnitUpdate]):
    
    def get_by_label(self, db: Session, *, label: str) -> Optional[Unit]:
        """Get unit by label (case-insensitive)."""
        return db.query(Unit).filter(Unit.label.ilike(label)).first()
    
    def get_by_status(
        self, db: Session, *, status: str, skip: int = 0, limit: int = 100
    ) -> List[Unit]:
        """Get units filtered by status."""
        return (
            db.query(Unit)
            .filter(Unit.status == status)
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_all(
        self, db: Session, *, status: Optional[str] = None, skip: int = 0, limit: int = 100
    ) -> List[Unit]:
        """Get all units, optionally filtered by status."""
        query = db.query(Unit)
        if status:
            query = query.filter(Unit.status == status)
        return query.offset(skip).limit(limit).all()
    
    def inactivate(self, db: Session, *, id: str) -> Optional[Unit]:
        """Soft delete: set status to inactive and deleted_at timestamp."""
        db_obj = self.get(db, id=id)
        if db_obj:
            db_obj.status = "inactive"
            db_obj.deleted_at = datetime.now(timezone.utc)
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
        return db_obj
    
    def label_exists(
        self, db: Session, *, label: str, exclude_id: Optional[str] = None
    ) -> bool:
        """Check if label already exists (for uniqueness validation)."""
        query = db.query(Unit).filter(Unit.label.ilike(label))
        if exclude_id:
            query = query.filter(Unit.id != exclude_id)
        return query.first() is not None


unit = CRUDUnit(Unit)
