import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, DateTime, Numeric, ForeignKey, Boolean, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

class VendorQuote(Base):
    __tablename__ = "vendor_quotes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    rfq_item_id: Mapped[str] = mapped_column(ForeignKey("rfq_items.id"), nullable=False)
    vendor_id: Mapped[str] = mapped_column(ForeignKey("vendors.id"), nullable=False)
    
    # 🔒 Internal Cost Data
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String, default="TWD")
    
    # 採購條件
    moq: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shipping_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(String, nullable=True)
    
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False)
    
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    rfq_item: Mapped["RFQItem"] = relationship(back_populates="vendor_quotes")
    vendor: Mapped["Vendor"] = relationship()
