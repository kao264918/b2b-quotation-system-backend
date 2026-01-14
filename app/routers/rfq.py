from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.models.rfq import RFQItem

router = APIRouter()


@router.post("/{rfq_id}/items/from-catalog", response_model=schemas.RFQItem, status_code=201)
def add_rfq_item_from_catalog(
    *,
    db: Session = Depends(get_db),
    rfq_id: str,
    item_in: schemas.RFQItemCreateFromCatalog
) -> Any:
    """
    Create RFQ Item from Catalog Item (Snapshot)
    
    - Validates Catalog Item exists
    - Creates snapshot with Catalog data
    - Output type requires length_cm and width_cm
    - Backend calculates area_unit
    
    Returns:
        201: RFQ Item created
        400: Validation failed (e.g., output missing dimensions)
        404: Catalog Item not found
    """
    # Verify RFQ exists
    rfq = crud.rfq.get(db, id=rfq_id)
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    
    try:
        rfq_item = crud.rfq.create_item_from_catalog(
            db,
            rfq_id=rfq_id,
            item_in=item_in
        )
        return rfq_item
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{rfq_id}/items/{item_id}", response_model=schemas.RFQItem)
def update_rfq_item(
    *,
    db: Session = Depends(get_db),
    rfq_id: str,
    item_id: str,
    item_in: schemas.RFQItemUpdate
) -> Any:
    """
    Update RFQ Item (Human Adjustment)
    
    - Allows modifying editable fields (name, unit, price, quantity, dimensions)
    - Immutable fields are ignored (catalog_item_id, source_item_no, type)
    - Output type: automatically recalculates area_unit when dimensions change
    
    Returns:
        200: RFQ Item updated
        404: RFQ or Item not found
    """
    # Get RFQ Item
    rfq_item = db.query(RFQItem).filter(
        RFQItem.id == item_id,
        RFQItem.rfq_id == rfq_id
    ).first()
    
    if not rfq_item:
        raise HTTPException(status_code=404, detail="RFQ Item not found")
    
    updated_item = crud.rfq.update_item_with_recalculation(
        db,
        db_obj=rfq_item,
        obj_in=item_in
    )
    return updated_item

