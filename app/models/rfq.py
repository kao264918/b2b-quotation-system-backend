import uuid
from datetime import datetime
from decimal import Decimal
from typing import List

from sqlalchemy import String, DateTime, Numeric, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

class RFQ(Base):
    __tablename__ = "rfqs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), nullable=False)
    
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    status: Mapped[str] = mapped_column(String, default="draft") # draft, sourcing, pricing, quoted, closed
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    items: Mapped[List["RFQItem"]] = relationship(back_populates="rfq", cascade="all, delete-orphan")
    customer: Mapped["Customer"] = relationship()

class RFQItem(Base):
    __tablename__ = "rfq_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    rfq_id: Mapped[str] = mapped_column(ForeignKey("rfqs.id"), nullable=False)
    
    # Snapshot from Catalog (immutable after creation)
    catalog_item_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_item_no: Mapped[str | None] = mapped_column(String, nullable=True)  # Catalog itemNo snapshot
    type: Mapped[str] = mapped_column(String, nullable=False)  # product / service / output
    
    # Editable fields (can be modified after creation)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False)
    
    # 🔒 Internal Only
    reference_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    
    # Customer-facing
    selling_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    tax_category: Mapped[str | None] = mapped_column(String, nullable=True) # ID or Code
    
    # Output type specific fields (material calculation)
    length_cm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    width_cm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    area_unit: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)  # Calculated by backend
    
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    rfq: Mapped["RFQ"] = relationship(back_populates="items")
    vendor_quotes: Mapped[List["VendorQuote"]] = relationship(back_populates="rfq_item", cascade="all, delete-orphan")

