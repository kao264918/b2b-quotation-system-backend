from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter()

@router.get("/", response_model=List[schemas.VendorQuote])
def read_vendor_quotes(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
) -> Any:
    return crud.vendor_quote.get_multi(db, skip=skip, limit=limit)

@router.post("/", response_model=schemas.VendorQuote)
def create_vendor_quote(
    *,
    db: Session = Depends(get_db),
    quote_in: schemas.VendorQuoteCreate
) -> Any:
    return crud.vendor_quote.create(db, obj_in=quote_in)

@router.get("/{id}", response_model=schemas.VendorQuote)
def read_vendor_quote(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    item = crud.vendor_quote.get(db, id=id)
    if not item:
        raise HTTPException(status_code=404, detail="Vendor Quote not found")
    return item

@router.put("/{id}", response_model=schemas.VendorQuote)
def update_vendor_quote(
    *,
    db: Session = Depends(get_db),
    id: str,
    quote_in: schemas.VendorQuoteUpdate
) -> Any:
    item = crud.vendor_quote.get(db, id=id)
    if not item:
        raise HTTPException(status_code=404, detail="Vendor Quote not found")
    return crud.vendor_quote.update(db, db_obj=item, obj_in=quote_in)
