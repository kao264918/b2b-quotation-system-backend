from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime
import math

from app.crud.base import CRUDBase
from app.models.catalog import CatalogItem
from app.schemas.catalog import CatalogItemCreate, CatalogItemUpdate


# Type to default unit mapping
TYPE_DEFAULT_UNITS = {
    "product": "pcs",
    "service": "pcs",
    "output": "材"
}


class CRUDCatalogItem(CRUDBase[CatalogItem, CatalogItemCreate, CatalogItemUpdate]):
    """CRUD operations for Catalog Item with MVP-compliant behaviors"""

    def generate_item_no(self, db: Session, item_type: str) -> str:
        """
        Generate ERP-style item number with concurrent safety.
        Format: P-0001, S-0001, O-0001
        Automatically expands beyond 4 digits when needed.
        """
        # Map type to prefix
        prefix_map = {
            "product": "P",
            "service": "S",
            "output": "O"
        }
        prefix = prefix_map.get(item_type, "P")

        # Use database-level lock to ensure concurrent safety
        # Query max item_no for this type WITH LOCK
        max_item = (
            db.query(CatalogItem)
            .filter(CatalogItem.item_no.like(f"{prefix}-%"))
            .with_for_update()  # Database row lock
            .order_by(CatalogItem.item_no.desc())
            .first()
        )

        if max_item:
            # Extract number from format "P-0001"
            try:
                last_num = int(max_item.item_no.split("-")[1])
                next_num = last_num + 1
            except (IndexError, ValueError):
                next_num = 1
        else:
            next_num = 1

        # Format with minimum 4 digits, auto-expand if needed
        num_str = str(next_num).zfill(max(4, len(str(next_num))))
        return f"{prefix}-{num_str}"

    def get_by_name(self, db: Session, *, name: str, exclude_id: Optional[str] = None) -> Optional[CatalogItem]:
        """
        Get catalog item by name for uniqueness validation.
        Checks across active, inactive, AND deleted items.
        """
        query = db.query(self.model).filter(self.model.name == name)
        if exclude_id:
            query = query.filter(self.model.id != exclude_id)
        return query.first()

    def get_multi_with_pagination(
        self,
        db: Session,
        *,
        page: int = 1,
        page_size: int = 50,
        status: Optional[str] = None,
        item_type: Optional[str] = None,
        search: Optional[str] = None
    ) -> Tuple[List[CatalogItem], int]:
        """
        Get paginated catalog items with filters.
        Always excludes soft-deleted items.
        Returns: (items, total_count)
        """
        # Base query: exclude deleted
        query = db.query(self.model).filter(self.model.deleted_at.is_(None))

        # Apply filters
        if status:
            query = query.filter(self.model.status == status)
        if item_type:
            query = query.filter(self.model.type == item_type)
        if search:
            # Fuzzy search on name
            query = query.filter(self.model.name.ilike(f"%{search}%"))

        # Get total count before pagination
        total_count = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        items = query.order_by(self.model.created_at.desc()).offset(offset).limit(page_size).all()

        return items, total_count

    def create_with_item_no(self, db: Session, *, obj_in: CatalogItemCreate) -> CatalogItem:
        """
        Create catalog item with auto-generated item_no.
        Validates name uniqueness and applies type-based default unit.
        """
        # Validate name uniqueness
        existing = self.get_by_name(db, name=obj_in.name)
        if existing:
            raise ValueError(f"Catalog item with name '{obj_in.name}' already exists")

        # Generate item_no
        item_no = self.generate_item_no(db, obj_in.type)

        # Apply default unit if not provided
        unit = obj_in.unit if obj_in.unit else TYPE_DEFAULT_UNITS.get(obj_in.type, "pcs")

        # Create object
        obj_data = obj_in.model_dump(exclude={"unit"})
        obj_data["unit"] = unit
        obj_data["item_no"] = item_no

        db_obj = self.model(**obj_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_with_validation(
        self, db: Session, *, db_obj: CatalogItem, obj_in: CatalogItemUpdate
    ) -> CatalogItem:
        """
        Update catalog item with name uniqueness validation.
        """
        # If name is being changed, validate uniqueness (excluding current item)
        if obj_in.name and obj_in.name != db_obj.name:
            existing = self.get_by_name(db, name=obj_in.name, exclude_id=db_obj.id)
            if existing:
                raise ValueError(f"Catalog item with name '{obj_in.name}' already exists")

        # Call base update method
        return self.update(db, db_obj=db_obj, obj_in=obj_in)

    def inactivate(self, db: Session, *, id: str) -> CatalogItem:
        """Set catalog item status to inactive"""
        obj = db.query(self.model).filter(self.model.id == id).first()
        if not obj:
            return None
        
        obj.status = "inactive"
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def reactivate(self, db: Session, *, id: str) -> CatalogItem:
        """Set catalog item status back to active"""
        obj = db.query(self.model).filter(self.model.id == id).first()
        if not obj:
            return None
        
        obj.status = "active"
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def soft_delete(self, db: Session, *, id: str) -> CatalogItem:
        """Soft delete: set deleted_at timestamp"""
        obj = db.query(self.model).filter(self.model.id == id).first()
        if not obj:
            return None
        
        obj.deleted_at = datetime.utcnow()
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def get(self, db: Session, id: str) -> Optional[CatalogItem]:
        """Override get to exclude deleted items"""
        return (
            db.query(self.model)
            .filter(and_(self.model.id == id, self.model.deleted_at.is_(None)))
            .first()
        )


catalog = CRUDCatalogItem(CatalogItem)

