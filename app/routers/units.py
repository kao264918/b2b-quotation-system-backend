from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter()


@router.get("/", response_model=List[schemas.Unit])
def read_units(
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None, description="Filter by status: active or inactive"),
    skip: int = 0,
    limit: int = 100
) -> Any:
    """
    Retrieve units.
    - If status is provided, filter by that status.
    - Otherwise return all units.
    """
    return crud.unit.get_all(db, status=status, skip=skip, limit=limit)


@router.post("/", response_model=schemas.Unit, status_code=201)
def create_unit(
    *,
    db: Session = Depends(get_db),
    unit_in: schemas.UnitCreate
) -> Any:
    """
    Create new unit.
    Returns 409 if label already exists.
    """
    if crud.unit.label_exists(db, label=unit_in.label):
        raise HTTPException(
            status_code=409,
            detail=f"Unit with label '{unit_in.label}' already exists"
        )
    return crud.unit.create(db, obj_in=unit_in)


@router.get("/{id}", response_model=schemas.Unit)
def read_unit(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    """Get unit by ID."""
    unit = crud.unit.get(db, id=id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    return unit


@router.put("/{id}", response_model=schemas.Unit)
def update_unit(
    *,
    db: Session = Depends(get_db),
    id: str,
    unit_in: schemas.UnitUpdate
) -> Any:
    """
    Update unit.
    Returns 409 if new label already exists on another unit.
    """
    unit = crud.unit.get(db, id=id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    
    # Check label uniqueness if updating label
    if unit_in.label and crud.unit.label_exists(db, label=unit_in.label, exclude_id=id):
        raise HTTPException(
            status_code=409,
            detail=f"Unit with label '{unit_in.label}' already exists"
        )
    
    return crud.unit.update(db, db_obj=unit, obj_in=unit_in)


@router.post("/{id}/inactivate", response_model=schemas.Unit)
def inactivate_unit(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    """
    Soft delete: mark unit as inactive.
    Does not actually delete the record.
    """
    unit = crud.unit.get(db, id=id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    
    if unit.status == "inactive":
        raise HTTPException(status_code=400, detail="Unit is already inactive")
    
    return crud.unit.inactivate(db, id=id)
