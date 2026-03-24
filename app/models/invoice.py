import uuid
from datetime import datetime
from decimal import Decimal
from typing import List

from sqlalchemy import String, DateTime, Numeric, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_number: Mapped[str] = mapped_column(String, unique=True, nullable=False)  # INV-YYMM-XXXX
    quote_id: Mapped[str] = mapped_column(ForeignKey("quotes.id"), nullable=False)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), nullable=False)
    
    status: Mapped[str] = mapped_column(String, default="draft")  # draft, issued, paid, void
    accounting_status: Mapped[str | None] = mapped_column(String, nullable=True)  # unpaid, paid
    
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    promotion_discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    promotion_code_snapshot: Mapped[str | None] = mapped_column(String, nullable=True)
    promotion_name_snapshot: Mapped[str | None] = mapped_column(String, nullable=True)
    promotion_type_snapshot: Mapped[str | None] = mapped_column(String(20), nullable=True)
    promotion_value_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    promotion_scope_snapshot: Mapped[str | None] = mapped_column(String(20), nullable=True)
    promotion_scope_category_snapshot: Mapped[str | None] = mapped_column(String, nullable=True)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # Soft delete

    # Relationships
    items: Mapped[List["InvoiceItem"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")
    quote: Mapped["Quote"] = relationship()
    customer: Mapped["Customer"] = relationship()


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    
    # 追溯用
    quote_item_id: Mapped[str | None] = mapped_column(String, nullable=True)
    
    # Snapshot 欄位
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    
    # 稅務 Snapshot
    tax_category_name: Mapped[str] = mapped_column(String, nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    
    # 計算欄位
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    
    # Deprecated
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Relationships
    invoice: Mapped["Invoice"] = relationship(back_populates="items")
