from typing import Any, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter()

@router.get("/quotes", response_model=List[schemas.QuoteTemplate])
def read_quote_templates(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
) -> Any:
    return crud.quote_template.get_multi(db, skip=skip, limit=limit)

@router.get("/invoices", response_model=List[schemas.InvoiceTemplate])
def read_invoice_templates(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
) -> Any:
    return crud.invoice_template.get_multi(db, skip=skip, limit=limit)
