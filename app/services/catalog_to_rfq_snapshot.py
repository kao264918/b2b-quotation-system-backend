"""
Catalog to RFQ Snapshot Service

Handles creating RFQ Items from Catalog Items with proper snapshotting.
Implements material calculation for output type items.
"""
from decimal import Decimal
from math import ceil
from typing import Optional
from sqlalchemy.orm import Session

from app.models.catalog import CatalogItem
from app.models.rfq import RFQItem


def calculate_area_unit(length_cm: Decimal, width_cm: Decimal) -> Decimal:
    """
    Calculate material area units (材數) - Backend Authority
    
    Formula: ceil((length_cm × width_cm) / 900)
    
    Args:
        length_cm: Length in centimeters
        width_cm: Width in centimeters
    
    Returns:
        Decimal: Material units (always rounded up)
    
    Examples:
        >>> calculate_area_unit(Decimal("90"), Decimal("100"))
        Decimal("10")  # 9000 / 900 = 10
        
        >>> calculate_area_unit(Decimal("50"), Decimal("100"))
        Decimal("6")   # 5000 / 900 = 5.55... → ceil = 6
    """
    area_sq_cm = length_cm * width_cm
    area_unit_raw = area_sq_cm / Decimal("900")
    return Decimal(ceil(float(area_unit_raw)))


def create_rfq_item_from_catalog(
    db: Session,
    *,
    rfq_id: str,
    catalog_item: CatalogItem,
    quantity: Decimal = Decimal("1"),
    length_cm: Optional[Decimal] = None,
    width_cm: Optional[Decimal] = None,
    unit_price_override: Optional[Decimal] = None,
    description_override: Optional[str] = None
) -> RFQItem:
    """
    Create RFQ Item from Catalog Item as snapshot
    
    Rules:
    1. Copy Catalog fields to RFQ Item
    2. Immutable fields: catalog_item_id, source_item_no, type
    3. Output type MUST provide length_cm, width_cm
    4. Backend calculates area_unit (frontend input ignored)
    
    Args:
        db: Database session
        rfq_id: Target RFQ ID
        catalog_item: Source Catalog Item
        quantity: Quantity (default: 1)
        length_cm: Length for output type (required if type=output)
        width_cm: Width for output type (required if type=output)
        unit_price_override: Override default_price
        description_override: Override description
    
    Returns:
        RFQItem: Created item with snapshot data
    
    Raises:
        ValueError: If output type missing dimensions
    """
    
    # Validate: Output type requires dimensions
    if catalog_item.type == "output":
        if not length_cm or not width_cm:
            raise ValueError("Output type requires length_cm and width_cm")
    
    # Calculate area_unit (only for output type)
    area_unit = None
    if catalog_item.type == "output" and length_cm and width_cm:
        area_unit = calculate_area_unit(length_cm, width_cm)
    
    # Create RFQ Item
    rfq_item = RFQItem(
        rfq_id=rfq_id,
        
        # ❌ Immutable fields (snapshot from Catalog)
        catalog_item_id=catalog_item.id,
        source_item_no=catalog_item.item_no,
        type=catalog_item.type,
        
        # ✅ Editable fields (initialized from Catalog)
        name=catalog_item.name,
        unit=catalog_item.unit,
        description=description_override if description_override is not None else catalog_item.description,
        quantity=quantity,
        
        # Pricing
        reference_cost=catalog_item.reference_cost,
        selling_price=unit_price_override if unit_price_override is not None else catalog_item.default_price,
        
        # Output type specific
        length_cm=length_cm,
        width_cm=width_cm,
        area_unit=area_unit,
        
        # Other
        tax_category=catalog_item.tax_category,
        notes=None
    )
    
    db.add(rfq_item)
    db.commit()
    db.refresh(rfq_item)
    return rfq_item


def update_rfq_item_with_recalculation(
    db: Session,
    *,
    db_obj: RFQItem,
    update_data: dict
) -> RFQItem:
    """
    Update RFQ Item and recalculate area_unit if dimensions changed
    
    Rules:
    1. Allow updating editable fields
    2. Block updating immutable fields (catalog_item_id, source_item_no, type)
    3. If output type and dimensions change → recalculate area_unit
    4. Frontend area_unit input is IGNORED
    
    Args:
        db: Database session
        db_obj: Existing RFQ Item
        update_data: Dict of fields to update
    
    Returns:
        RFQItem: Updated item
    """
    
    # Remove immutable fields if present (safety)
    immutable_fields = ['catalog_item_id', 'source_item_no', 'type', 'area_unit']
    for field in immutable_fields:
        update_data.pop(field, None)
    
    # If Output type and dimensions changed → recalculate
    if db_obj.type == "output":
        length_cm = update_data.get("length_cm", db_obj.length_cm)
        width_cm = update_data.get("width_cm", db_obj.width_cm)
        
        if length_cm and width_cm:
            update_data["area_unit"] = calculate_area_unit(length_cm, width_cm)
    
    # Apply updates
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    
    db.commit()
    db.refresh(db_obj)
    return db_obj
