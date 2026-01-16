"""
RFQ CRUD Operations (Versioned)

Implements the versioned RFQ model where:
- RFQ is the master record
- RFQVersion stores immutable snapshots
- Every update creates a new version
"""
from typing import Any, Dict, List, Optional
from decimal import Decimal
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from app.models.rfq import RFQ, RFQVersion, RFQItem, RFQStatus, TaxSetting
from app.models.vendor import Vendor
from app.schemas.rfq import (
    RFQCreate, RFQUpdate, RFQItemCreate, RFQStatusUpdate,
    VendorSnapshot, RFQListItemResponse
)
from app.services.rfq_number import generate_rfq_number
from app.services.rfq_calculation import recalculate_rfq_item, calculate_item_totals


def create_vendor_snapshot(vendor: Vendor) -> dict:
    """Create vendor snapshot dict from Vendor model."""
    primary_contact = None
    primary_contact_phone = None
    
    if vendor.contacts:
        for contact in vendor.contacts:
            if contact.is_primary:
                primary_contact = contact.name
                primary_contact_phone = contact.phone
                break
    
    return {
        "id": vendor.id,
        "name": vendor.name,
        "company_name": vendor.company_name,
        "tax_id": vendor.tax_id,
        "email": vendor.email,
        "phone": vendor.phone,
        "address": vendor.address,
        "primary_contact_name": primary_contact,
        "primary_contact_phone": primary_contact_phone,
    }


def create_rfq(db: Session, *, obj_in: RFQCreate) -> RFQ:
    """
    Create a new RFQ with initial version (v1).
    
    1. Generate RFQ number
    2. Create RFQ master record
    3. Create initial version with vendor snapshot
    4. Create items with calculations
    """
    # Get vendor for snapshot
    vendor = db.query(Vendor).filter(Vendor.id == obj_in.vendor_id).first()
    if not vendor:
        raise ValueError(f"Vendor {obj_in.vendor_id} not found")
    
    # Generate RFQ number
    rfq_no = generate_rfq_number(db)
    
    # Create RFQ master
    rfq = RFQ(
        rfq_no=rfq_no,
        project_name=obj_in.project_name,
        vendor_id=obj_in.vendor_id,
        status=RFQStatus.DRAFT.value,
    )
    db.add(rfq)
    db.flush()  # Get rfq.id
    
    # Create initial version
    vendor_snapshot = create_vendor_snapshot(vendor)
    
    version = RFQVersion(
        rfq_id=rfq.id,
        version_number=1,
        vendor_snapshot=vendor_snapshot,
        project_name=obj_in.project_name,
        required_date=obj_in.required_date,
        tax_setting=obj_in.tax_setting or TaxSetting.NON_TAXABLE.value,
        notes=obj_in.notes or "Initial version",
    )
    db.add(version)
    db.flush()  # Get version.id
    
    # Create items with calculations
    items_data = []
    for idx, item_in in enumerate(obj_in.items or []):
        item_dict = item_in.model_dump()
        item_dict["sort_order"] = idx
        item_dict = recalculate_rfq_item(item_dict)
        
        item = RFQItem(
            rfq_version_id=version.id,
            **item_dict
        )
        db.add(item)
        items_data.append(item_dict)
    
    # Calculate version totals
    totals = calculate_item_totals(items_data, version.tax_setting)
    version.subtotal = totals["subtotal"]
    version.tax_amount = totals["tax_amount"]
    version.total_amount = totals["total_amount"]
    
    # Update RFQ with current version
    rfq.current_version_id = version.id
    
    db.commit()
    db.refresh(rfq)
    
    return rfq


def get_rfq(db: Session, rfq_id: str) -> Optional[RFQ]:
    """Get RFQ by ID with eager loading of current version."""
    return db.query(RFQ).options(
        joinedload(RFQ.versions).joinedload(RFQVersion.items)
    ).filter(RFQ.id == rfq_id).first()


def get_rfq_by_no(db: Session, rfq_no: str) -> Optional[RFQ]:
    """Get RFQ by RFQ number."""
    return db.query(RFQ).filter(RFQ.rfq_no == rfq_no).first()


def get_rfqs(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    status: Optional[str] = None
) -> List[RFQ]:
    """Get list of RFQs with optional filtering."""
    query = db.query(RFQ).options(
        joinedload(RFQ.vendor)
    )
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (RFQ.rfq_no.ilike(search_term)) |
            (RFQ.project_name.ilike(search_term))
        )
    
    if status:
        query = query.filter(RFQ.status == status)
    
    return query.order_by(desc(RFQ.updated_at)).offset(skip).limit(limit).all()


def count_rfqs(
    db: Session,
    *,
    search: Optional[str] = None,
    status: Optional[str] = None
) -> int:
    """Count RFQs with optional filtering."""
    query = db.query(RFQ)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (RFQ.rfq_no.ilike(search_term)) |
            (RFQ.project_name.ilike(search_term))
        )
    
    if status:
        query = query.filter(RFQ.status == status)
    
    return query.count()


def get_version(db: Session, version_id: str) -> Optional[RFQVersion]:
    """Get specific version with items."""
    return db.query(RFQVersion).options(
        joinedload(RFQVersion.items)
    ).filter(RFQVersion.id == version_id).first()


def get_versions(db: Session, rfq_id: str) -> List[RFQVersion]:
    """Get all versions for an RFQ."""
    return db.query(RFQVersion).filter(
        RFQVersion.rfq_id == rfq_id
    ).order_by(desc(RFQVersion.version_number)).all()


def create_new_version(
    db: Session,
    *,
    rfq: RFQ,
    obj_in: RFQUpdate
) -> RFQVersion:
    """
    Create a new version of an RFQ.
    
    Copies current version and applies updates.
    """
    # Get current version
    current = get_version(db, rfq.current_version_id)
    if not current:
        raise ValueError("Current version not found")
    
    # Get latest version number
    latest = db.query(RFQVersion).filter(
        RFQVersion.rfq_id == rfq.id
    ).order_by(desc(RFQVersion.version_number)).first()
    next_version = (latest.version_number if latest else 0) + 1
    
    # Create new version
    version = RFQVersion(
        rfq_id=rfq.id,
        version_number=next_version,
        vendor_snapshot=current.vendor_snapshot,  # Keep same vendor
        project_name=obj_in.project_name or current.project_name,
        required_date=obj_in.required_date if obj_in.required_date is not None else current.required_date,
        tax_setting=obj_in.tax_setting or current.tax_setting,
        notes=obj_in.notes,  # Required for new versions
    )
    db.add(version)
    db.flush()
    
    # Copy or update items
    items_data = []
    if obj_in.items is not None:
        # Use provided items
        for idx, item_in in enumerate(obj_in.items):
            item_dict = item_in.model_dump()
            item_dict["sort_order"] = idx
            item_dict = recalculate_rfq_item(item_dict)
            
            item = RFQItem(rfq_version_id=version.id, **item_dict)
            db.add(item)
            items_data.append(item_dict)
    else:
        # Copy from current version
        for old_item in current.items:
            item_dict = {
                "catalog_item_id": old_item.catalog_item_id,
                "source_item_no": old_item.source_item_no,
                "item_type": old_item.item_type,
                "name": old_item.name,
                "description": old_item.description,
                "spec_notes": old_item.spec_notes,
                "quantity": old_item.quantity,
                "unit": old_item.unit,
                "unit_price": old_item.unit_price,
                "length_cm": old_item.length_cm,
                "width_cm": old_item.width_cm,
                "sort_order": old_item.sort_order,
            }
            item_dict = recalculate_rfq_item(item_dict)
            
            item = RFQItem(rfq_version_id=version.id, **item_dict)
            db.add(item)
            items_data.append(item_dict)
    
    # Calculate totals
    totals = calculate_item_totals(items_data, version.tax_setting)
    version.subtotal = totals["subtotal"]
    version.tax_amount = totals["tax_amount"]
    version.total_amount = totals["total_amount"]
    
    # Update RFQ current version
    rfq.current_version_id = version.id
    if obj_in.project_name:
        rfq.project_name = obj_in.project_name
    
    db.commit()
    db.refresh(version)
    
    return version


def update_status(db: Session, *, rfq: RFQ, status: str) -> RFQ:
    """Update RFQ status."""
    rfq.status = status
    db.commit()
    db.refresh(rfq)
    return rfq


def select_final_version(db: Session, *, rfq: RFQ, version_id: str) -> RFQ:
    """Select a version as the final version."""
    # Verify version exists and belongs to this RFQ
    version = db.query(RFQVersion).filter(
        RFQVersion.id == version_id,
        RFQVersion.rfq_id == rfq.id
    ).first()
    
    if not version:
        raise ValueError("Version not found")
    
    rfq.selected_version_id = version_id
    db.commit()
    db.refresh(rfq)
    return rfq


def delete_rfq(db: Session, rfq_id: str) -> bool:
    """Delete RFQ and all versions."""
    rfq = db.query(RFQ).filter(RFQ.id == rfq_id).first()
    if not rfq:
        return False
    
    db.delete(rfq)
    db.commit()
    return True
