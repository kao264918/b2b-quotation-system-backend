"""
RFQ (Request for Quotation) Models - Vendor Inquiry System

Implements a versioned RFQ system where:
- RFQ is the master record (header info + current/selected version pointers)
- RFQVersion stores immutable snapshots of vendor data, items, and calculations
- RFQItem stores line items with dimension-based calculations

Key Rules:
- RFQ No format: RFQ-YYMM-SEQ (e.g., RFQ-2601-001)
- Every edit creates a new version (immutable snapshot pattern)
- Vendor data is snapshotted at version creation time
- Calculations (area_unit, subtotal, tax, total) are backend-authoritative
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import String, DateTime, Numeric, ForeignKey, Text, Integer, Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class RFQStatus(str, enum.Enum):
    """RFQ workflow stages (manually updated by user)"""
    DRAFT = "draft"
    VENDOR_QUOTING = "vendor_quoting"
    FINALIZED = "finalized"
    WON = "won"
    LOST = "lost"


class TaxSetting(str, enum.Enum):
    """Order-level tax options"""
    TAXABLE_5 = "taxable_5"      # 應稅 5%
    TAXABLE_10 = "taxable_10"    # 應稅 10%
    NON_TAXABLE = "non_taxable"  # 未稅 0%
    TAX_EXEMPT = "tax_exempt"    # 免稅


class RFQ(Base):
    """
    Master RFQ record.
    Points to current working version and optionally a selected (final) version.
    """
    __tablename__ = "rfqs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Auto-generated: RFQ-YYMM-SEQ
    rfq_no: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    
    # Project info (denormalized from current version for list queries)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Link to vendor master (for reference only; actual data is snapshotted in version)
    vendor_id: Mapped[str] = mapped_column(ForeignKey("vendors.id"), nullable=False)
    
    # Version pointers
    current_version_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    selected_version_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # Final version
    
    # Workflow stage
    status: Mapped[str] = mapped_column(
        String(20), 
        default=RFQStatus.DRAFT.value,
        nullable=False
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    vendor: Mapped["Vendor"] = relationship("Vendor")
    versions: Mapped[List["RFQVersion"]] = relationship(
        "RFQVersion", 
        back_populates="rfq", 
        cascade="all, delete-orphan",
        order_by="RFQVersion.version_number.desc()"
    )


class RFQVersion(Base):
    """
    Immutable snapshot of an RFQ at a point in time.
    Once created, should not be modified (except for notes).
    """
    __tablename__ = "rfq_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    rfq_id: Mapped[str] = mapped_column(ForeignKey("rfqs.id"), nullable=False)
    
    # Sequential version number within this RFQ
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    
    # Vendor snapshot (full dump at creation time)
    vendor_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    
    # Project details at this version
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    required_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Tax setting for this version
    tax_setting: Mapped[str] = mapped_column(
        String(20),
        default=TaxSetting.NON_TAXABLE.value,
        nullable=False
    )
    
    # Currency (default TWD)
    currency: Mapped[str] = mapped_column(String(10), default="TWD", nullable=False)
    
    # Calculated totals (backend-authoritative)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"), nullable=False)
    
    # Version notes (why this version was created)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # User ID for audit

    # Relationships
    rfq: Mapped["RFQ"] = relationship("RFQ", back_populates="versions")
    items: Mapped[List["RFQItem"]] = relationship(
        "RFQItem",
        back_populates="version",
        cascade="all, delete-orphan",
        order_by="RFQItem.sort_order"
    )


class RFQItem(Base):
    """
    Line item within an RFQ version.
    Supports three types: product, service, output (with dimension calculation).
    """
    __tablename__ = "rfq_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    rfq_version_id: Mapped[str] = mapped_column(ForeignKey("rfq_versions.id"), nullable=False)
    
    # Sort order for display
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Snapshot from Catalog (if created from catalog)
    catalog_item_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_item_no: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    # Item type: product, service, output
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Core fields
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    spec_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Quantity & Unit
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=Decimal("1"))
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="pcs")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=Decimal("0"))
    
    # Output type: Dimension fields (for area calculation)
    length_cm: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    width_cm: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    
    # Calculated: ceil((length * width) / 900) - for output type only
    area_unit: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    
    # Line subtotal: unit_price * quantity * (area_unit if output else 1)
    line_subtotal: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"), nullable=False)

    # Relationships
    version: Mapped["RFQVersion"] = relationship("RFQVersion", back_populates="items")
    vendor_quotes: Mapped[List["VendorQuote"]] = relationship("VendorQuote", back_populates="rfq_item", cascade="all, delete-orphan")


# Import for type hints only (avoid circular imports)
from app.models.vendor import Vendor
from app.models.vendor_quote import VendorQuote
