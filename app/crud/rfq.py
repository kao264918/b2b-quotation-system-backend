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

from app.models.rfq import RFQ, RFQVersion, RFQItem, RFQStatus, AccountingStatus, TaxSetting
from app.models.customer import Customer
from app.schemas.rfq import (
    RFQCreate, RFQUpdate, RFQItemCreate, RFQStatusUpdate,
    VendorSnapshot, RFQListItemResponse
)
from app.services.rfq_number import generate_rfq_number
from app.services.rfq_calculation import recalculate_rfq_item, calculate_item_totals


def create_vendor_snapshot(vendor: Customer) -> dict:
    """Create vendor snapshot dict from Customer model (acting as Vendor)."""
    # Customer model currently has flat contact structure (contact_name, contact_email, etc.)
    # The Vendor model had valid contacts list.
    # Future: Customer might need contacts list. For now map flat fields.
    
    primary_contact_name = vendor.contact_name
    primary_contact_phone = vendor.contact_phone
    primary_contact_email = vendor.contact_email
    
    return {
        "id": vendor.id,
        "name": vendor.company_name, # Snapshot expects name/company_name
        "company_name": vendor.company_name,
        "tax_id": vendor.tax_id,
        "email": vendor.company_email or vendor.contact_email, # prefer company email if exists
        "phone": vendor.contact_phone, # Use contact phone as main phone? or is there a company phone? Customer has contact_phone.
        "address": vendor.address_line1,
        "primary_contact_name": primary_contact_name,
        "primary_contact_phone": primary_contact_phone,
        "primary_contact_email": primary_contact_email,
        "currency": vendor.default_currency or "TWD",
        "payment_terms": vendor.default_payment_terms
    }


def create_rfq(db: Session, *, obj_in: RFQCreate) -> RFQ:
    """
    Create a new RFQ with initial version (v1).
    
    1. Generate RFQ number
    2. Create RFQ master record
    3. Create initial version with vendor snapshot
    4. Create items with calculations
    """
    # Get vendor (Customer) for snapshot
    vendor = db.query(Customer).filter(Customer.id == obj_in.vendor_id).first()
    if not vendor:
        raise ValueError(f"Vendor (Customer) {obj_in.vendor_id} not found")
    
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
    """Get RFQ by ID with eager loading of current version. Excludes soft-deleted."""
    return db.query(RFQ).options(
        joinedload(RFQ.versions).joinedload(RFQVersion.items)
    ).filter(RFQ.id == rfq_id, RFQ.deleted_at.is_(None)).first()


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
    """Get list of RFQs with optional filtering. Excludes soft-deleted."""
    query = db.query(RFQ).options(
        joinedload(RFQ.vendor)
    ).filter(RFQ.deleted_at.is_(None))
    
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
    """Count RFQs with optional filtering. Excludes soft-deleted."""
    query = db.query(RFQ).filter(RFQ.deleted_at.is_(None))
    
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
    
    # -------------------------------------------------------------------------
    # Diff Logic (Section 3.1)
    # -------------------------------------------------------------------------
    
    # helper to check if items changed
    def items_changed(new_items: List[RFQItemCreate], old_items: List[RFQItem]) -> bool:
        if new_items is None:
            return False # No new items provided means no change intended (or assume keep same)
            
        if len(new_items) != len(old_items):
            return True
            
        # Compare each item (assuming order matters or sort by some key?)
        # Frontend sends items in order.
        # We need to compare field by field.
        for i, new_item in enumerate(new_items):
            old_item = old_items[i]
            # Compare material fields
            # Note: new_item is Pydantic, old_item is SQLAlchemy
            # Check ID match if possible? No, strictly content.
            if new_item.name != old_item.name: return True
            if new_item.item_type != old_item.item_type: return True
            if new_item.quantity != old_item.quantity: return True
            if new_item.unit != old_item.unit: return True
            if new_item.unit_price != old_item.unit_price: return True
            # Handle optionals/None vs 0
            if (new_item.length_cm or 0) != (old_item.length_cm or 0): return True
            if (new_item.width_cm or 0) != (old_item.width_cm or 0): return True
            if (new_item.spec_notes or "") != (old_item.spec_notes or ""): return True
            
        return False

    has_item_changes = obj_in.items is not None and items_changed(obj_in.items, current.items)
    
    # Check header changes
    new_tax = obj_in.tax_setting if obj_in.tax_setting is not None else current.tax_setting
    tax_changed = new_tax != current.tax_setting
    
    new_project_name = obj_in.project_name if obj_in.project_name is not None else current.project_name
    name_changed = new_project_name != current.project_name
    
    new_date = obj_in.required_date if obj_in.required_date is not None else current.required_date
    date_changed = new_date != current.required_date
    
    # Check if ANY material change exists
    if not (has_item_changes or tax_changed or name_changed or date_changed):
        # No material changes, return current version (Idempotency)
        return current

    # -------------------------------------------------------------------------
    # Auto-Notes Logic (Section 3.2)
    # -------------------------------------------------------------------------
    system_notes = []
    if tax_changed:
        system_notes.append("Tax Change") # Explicit tax log
    if has_item_changes:
        system_notes.append("Updated Line Items") # Separate item log
    if name_changed:
        system_notes.append("Project Name Change")
        
    final_notes = obj_in.notes or ""
    if system_notes:
        auto_note = f"[{', '.join(system_notes)}]"
        if final_notes:
            final_notes = f"{auto_note} {final_notes}"
        else:
            final_notes = auto_note

    # -------------------------------------------------------------------------
    # Create Version
    # -------------------------------------------------------------------------

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
        project_name=new_project_name,
        required_date=new_date,
        tax_setting=new_tax,
        notes=final_notes, 
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
            # validata_output_dims called in router, so we assume valid or allow DB to enforce?
            # Router validated it because we have id/mapping requirement.
            
            item_dict = recalculate_rfq_item(item_dict)
            
            # Remove 'id' if present in model_dump (it's for validation mapping only)
            if 'id' in item_dict:
                del item_dict['id']

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
    if name_changed:
        rfq.project_name = new_project_name
    
    # B4: Log audit trail for tax setting changes
    # (We already handle "Tax Change" in notes, but keeping the explicit Entity Audit Log is good too as requested)
    if tax_changed:
        from app.crud import audit_log
        tax_labels = {
            "taxable_5": "應稅 (5%)",
            "taxable_10": "應稅 (10%)",
            "non_taxable": "未稅 (0%)",
            "tax_exempt": "免稅"
        }
        old_label = tax_labels.get(current.tax_setting, current.tax_setting)
        new_label = tax_labels.get(new_tax, new_tax)
        audit_log.log_action(
            db,
            entity_type="rfq",
            entity_id=rfq.id,
            action="update",
            changes={
                "field": "稅金設定",
                "old_value": old_label,
                "new_value": new_label,
                "version": next_version
            }
        )
    
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
    """
    Select a version as the final version.
    Also sets RFQ status to FINALIZED.
    """
    # Verify version exists and belongs to this RFQ
    version = db.query(RFQVersion).filter(
        RFQVersion.id == version_id,
        RFQVersion.rfq_id == rfq.id
    ).first()
    
    if not version:
        raise ValueError("Version not found")
    
    rfq.selected_version_id = version_id
    rfq.status = RFQStatus.FINALIZED.value
    db.commit()
    db.refresh(rfq)
    return rfq


def revert_rfq(db: Session, *, rfq: RFQ, notes: str = "Reverted from finalized") -> RFQVersion:
    """
    Revert a FINALIZED RFQ to VENDOR_QUOTING.
    Creates a new version from the selected (final) version.
    
    Precondition: RFQ must be in FINALIZED status.
    """
    allowed_for_revert = [RFQStatus.FINALIZED.value, RFQStatus.CLOSED.value, RFQStatus.DISCARDED.value]
    if rfq.status not in allowed_for_revert:
        raise ValueError("Can only revert from FINALIZED, CLOSED, or DISCARDED status")
    
    if not rfq.selected_version_id:
        # Fallback to current version if selected is missing (robustness)
        rfq.selected_version_id = rfq.current_version_id
        
    if not rfq.selected_version_id:
        raise ValueError("No version available to revert from")
    
    # Get the current final version
    final_version = get_version(db, rfq.selected_version_id)
    if not final_version:
        raise ValueError("Selected version not found")
    
    # Get next version number
    latest = db.query(RFQVersion).filter(
        RFQVersion.rfq_id == rfq.id
    ).order_by(desc(RFQVersion.version_number)).first()
    next_version_num = (latest.version_number if latest else 0) + 1
    
    # Create new version from the final version
    new_version = RFQVersion(
        rfq_id=rfq.id,
        version_number=next_version_num,
        vendor_snapshot=final_version.vendor_snapshot,
        project_name=final_version.project_name,
        required_date=final_version.required_date,
        tax_setting=final_version.tax_setting,
        currency=final_version.currency,
        notes=notes,
    )
    db.add(new_version)
    db.flush()
    
    # Copy items from final version
    items_data = []
    for old_item in final_version.items:
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
        
        item = RFQItem(rfq_version_id=new_version.id, **item_dict)
        db.add(item)
        items_data.append(item_dict)
    
    # Calculate totals
    totals = calculate_item_totals(items_data, new_version.tax_setting)
    new_version.subtotal = totals["subtotal"]
    new_version.tax_amount = totals["tax_amount"]
    new_version.total_amount = totals["total_amount"]
    
    # Update RFQ: change status, update current version, clear selected
    rfq.status = RFQStatus.VENDOR_QUOTING.value
    rfq.current_version_id = new_version.id
    # Note: selected_version_id is kept for history reference
    
    db.commit()
    db.refresh(new_version)
    return new_version


def update_accounting_status(db: Session, *, rfq: RFQ, accounting_status: str) -> RFQ:
    """
    Update accounting status independently of workflow status.
    """
    rfq.accounting_status = accounting_status
    db.commit()
    db.refresh(rfq)
    return rfq


def delete_rfq(db: Session, rfq_id: str) -> bool:
    """
    Soft delete RFQ (set deleted_at timestamp).
    Any status can be deleted per Master Spec.
    """
    from datetime import datetime, timezone
    
    rfq = db.query(RFQ).filter(RFQ.id == rfq_id, RFQ.deleted_at.is_(None)).first()
    if not rfq:
        return False
    
    # Soft delete: set deleted_at timestamp
    rfq.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return True
