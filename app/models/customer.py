import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Customer(Base):
    """Customer model aligned to CUSTOMER_FIELD_SPEC.md v1.2"""
    __tablename__ = "customers"

    # System Fields
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    status: Mapped[str] = mapped_column(String, default="active")  # active | inactive
    roles: Mapped[list[str]] = mapped_column(JSON, default=["customer"])  # customer, vendor

    # Company Information
    company_name: Mapped[str] = mapped_column(String, nullable=False)
    company_email: Mapped[str | None] = mapped_column(String, nullable=True)
    tax_id: Mapped[str] = mapped_column(String, nullable=False)
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    website: Mapped[str | None] = mapped_column(String, nullable=True)

    # Address Information
    address_line1: Mapped[str] = mapped_column(String, nullable=False)
    address_line2: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str] = mapped_column(String, nullable=False)
    postal_code: Mapped[str | None] = mapped_column(String, nullable=True)
    country: Mapped[str] = mapped_column(String, nullable=False)

    # Primary Contact
    contact_name: Mapped[str] = mapped_column(String, nullable=False)
    contact_email: Mapped[str] = mapped_column(String, nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    contact_title: Mapped[str | None] = mapped_column(String, nullable=True)

    # Billing & Internal
    billing_email: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
