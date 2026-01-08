import uuid
from datetime import datetime
from typing import List

from sqlalchemy import String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    company_name: Mapped[str] = mapped_column(String, nullable=False)
    tax_id: Mapped[str | None] = mapped_column(String, nullable=True)
    
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    
    default_payment_terms: Mapped[str | None] = mapped_column(String, nullable=True)
    default_currency: Mapped[str | None] = mapped_column(String, default="TWD")
    
    status: Mapped[str] = mapped_column(String, default="active") # active, inactive
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    contacts: Mapped[List["VendorContact"]] = relationship(back_populates="vendor", cascade="all, delete-orphan")

class VendorContact(Base):
    __tablename__ = "vendor_contacts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    vendor_id: Mapped[str] = mapped_column(ForeignKey("vendors.id"), nullable=False)
    
    name: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    vendor: Mapped["Vendor"] = relationship(back_populates="contacts")
