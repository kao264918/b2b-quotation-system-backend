import uuid
from datetime import datetime
from decimal import Decimal
from typing import List

from sqlalchemy import String, DateTime, Numeric, ForeignKey, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base
from typing import Optional, Dict

class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    rfq_id: Mapped[str | None] = mapped_column(ForeignKey("rfqs.id"), nullable=True)  # Nullable for standalone quotes
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), nullable=False)
    
    title: Mapped[str] = mapped_column(String, nullable=False)
    quote_number: Mapped[str] = mapped_column(String, unique=True, nullable=False, default=lambda: f"QUO-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}")
    
    # Status fields
    status: Mapped[str] = mapped_column(String, default="draft")  # draft, confirmed, closed, discarded
    accounting_status: Mapped[str | None] = mapped_column(String, nullable=True)  # unpaid, paid (null for draft)
    version: Mapped[int] = mapped_column(Integer, default=1)  # Version number for tracking changes
    
    # Tax setting (order-level)
    tax_setting: Mapped[str] = mapped_column(String(20), default="taxable_5")  # taxable_5, taxable_10, non_taxable, tax_exempt
    
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    cost_status: Mapped[str] = mapped_column(String(20), default="ok")  # ok | missing
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    gross_profit_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    gross_profit_rate: Mapped[Decimal] = mapped_column(Numeric(7, 2), default=0)
    
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    items: Mapped[List["QuoteItem"]] = relationship(back_populates="quote", cascade="all, delete-orphan")
    rfq: Mapped["RFQ"] = relationship()
    customer: Mapped["Customer"] = relationship()

class QuoteItem(Base):
    __tablename__ = "quote_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    quote_id: Mapped[str] = mapped_column(ForeignKey("quotes.id"), nullable=False)
    
    # 追溯用（可選，不做同步）
    rfq_item_id: Mapped[str | None] = mapped_column(String, nullable=True)
    catalog_item_id: Mapped[str | None] = mapped_column(String, nullable=True)
    
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
    snapshot_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Relationships
    # Relationships
    quote: Mapped["Quote"] = relationship(back_populates="items")
    rfq_item: Mapped["RFQItem"] = relationship("RFQItem", primaryjoin="foreign(QuoteItem.rfq_item_id) == remote(RFQItem.id)", viewonly=True)

    @property
    def source_rfq_info(self) -> Optional[Dict[str, str]]:
        if self.rfq_item and self.rfq_item.version and self.rfq_item.version.rfq:
            return {
                "rfq_no": self.rfq_item.version.rfq.rfq_no,
                "project_name": self.rfq_item.version.rfq.project_name
            }
        return None
