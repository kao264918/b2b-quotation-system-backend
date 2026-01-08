from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter()

@router.get("/", response_model=List[schemas.Quote])
def read_quotes(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
) -> Any:
    return crud.quote.get_multi(db, skip=skip, limit=limit)

@router.post("/", response_model=schemas.Quote)
def create_quote(
    *,
    db: Session = Depends(get_db),
    quote_in: schemas.QuoteCreate
) -> Any:
    return crud.quote.create(db, obj_in=quote_in)

@router.get("/{id}", response_model=schemas.Quote)
def read_quote(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    quote = crud.quote.get(db, id=id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return quote

@router.put("/{id}", response_model=schemas.Quote)
def update_quote(
    *,
    db: Session = Depends(get_db),
    id: str,
    quote_in: schemas.QuoteUpdate
) -> Any:
    quote = crud.quote.get(db, id=id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    # Check status constraints here if needed
    return crud.quote.update(db, db_obj=quote, obj_in=quote_in)

@router.post("/{id}/create-invoice", response_model=schemas.Invoice)
def create_invoice_from_quote(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    from app.services import snapshot
    return snapshot.create_invoice_from_quote(db, quote_id=id)

# Status Actions
@router.post("/{id}/send", response_model=schemas.Quote)
def send_quote(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    quote = crud.quote.get(db, id=id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    if quote.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft quotes can be sent")
    
    from datetime import datetime
    update_data = {"status": "sent", "sent_at": datetime.now()}
    return crud.quote.update(db, db_obj=quote, obj_in=update_data)
