from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter()

@router.get("/", response_model=List[schemas.Invoice])
def read_invoices(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
) -> Any:
    return crud.invoice.get_multi(db, skip=skip, limit=limit)

@router.post("/", response_model=schemas.Invoice)
def create_invoice(
    *,
    db: Session = Depends(get_db),
    invoice_in: schemas.InvoiceCreate
) -> Any:
    return crud.invoice.create(db, obj_in=invoice_in)

@router.get("/{id}", response_model=schemas.Invoice)
def read_invoice(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    invoice = crud.invoice.get(db, id=id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice

@router.put("/{id}", response_model=schemas.Invoice)
def update_invoice(
    *,
    db: Session = Depends(get_db),
    id: str,
    invoice_in: schemas.InvoiceUpdate
) -> Any:
    invoice = crud.invoice.get(db, id=id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return crud.invoice.update(db, db_obj=invoice, obj_in=invoice_in)

@router.post("/{id}/issue", response_model=schemas.Invoice)
def issue_invoice(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    invoice = crud.invoice.get(db, id=id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft invoices can be issued")
        
    from datetime import datetime
    update_data = {"status": "issued", "issued_at": datetime.now()}
    return crud.invoice.update(db, db_obj=invoice, obj_in=update_data)
