import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, DateTime, Numeric, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base

class CatalogItem(Base):
    """Catalog Item Model - MVP aligned to CATALOG_BACKEND_EXECUTION_GUIDE"""
    __tablename__ = "catalog_items"
    
    __table_args__ = (
        UniqueConstraint('name', name='uq_catalog_item_name'),
        UniqueConstraint('item_no', name='uq_catalog_item_item_no'),
        Index('ix_catalog_items_status', 'status'),
        Index('ix_catalog_items_type', 'type'),
        Index('ix_catalog_items_deleted_at', 'deleted_at'),
    )

    # System Fields
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    item_no: Mapped[str] = mapped_column(String, nullable=False, unique=True)  # ERP-style: P-0001, S-0001, O-0001
    
    # Required Fields
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    type: Mapped[str] = mapped_column(String, nullable=False)  # 'product' | 'service' | 'output'
    unit: Mapped[str] = mapped_column(String, nullable=False)
    reference_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)  # 🔒 Internal Only
    default_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    
    # Optional Fields
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    tax_category: Mapped[str | None] = mapped_column(String, nullable=True)  # ID or Code
    
    # Status & Audit
    status: Mapped[str] = mapped_column(String, default="active")  # 'active' | 'inactive'
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # Soft delete
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
