from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter()

@router.get("/", response_model=List[schemas.Vendor])
def read_vendors(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = Query(None, description="Search by name or company name")
) -> Any:
    """
    Get vendors with optional search filter.
    Search matches name or company_name (case-insensitive).
    """
    return crud.vendor.get_multi(db, skip=skip, limit=limit, search=search)

@router.post("/", response_model=schemas.Vendor)
def create_vendor(
    *,
    db: Session = Depends(get_db),
    vendor_in: schemas.VendorCreate
) -> Any:
    return crud.vendor.create(db, obj_in=vendor_in)

@router.get("/{id}", response_model=schemas.Vendor)
def read_vendor(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    vendor = crud.vendor.get(db, id=id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor

@router.put("/{id}", response_model=schemas.Vendor)
def update_vendor(
    *,
    db: Session = Depends(get_db),
    id: str,
    vendor_in: schemas.VendorUpdate
) -> Any:
    vendor = crud.vendor.get(db, id=id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return crud.vendor.update(db, db_obj=vendor, obj_in=vendor_in)

@router.delete("/{id}", response_model=schemas.Vendor)
def delete_vendor(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    vendor = crud.vendor.get(db, id=id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return crud.vendor.remove(db, id=id)
