from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter()

@router.get("/", response_model=List[schemas.RFQ])
def read_rfqs(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
) -> Any:
    return crud.rfq.get_multi(db, skip=skip, limit=limit)

@router.post("/", response_model=schemas.RFQ)
def create_rfq(
    *,
    db: Session = Depends(get_db),
    rfq_in: schemas.RFQCreate
) -> Any:
    return crud.rfq.create(db, obj_in=rfq_in)

@router.get("/{id}", response_model=schemas.RFQ)
def read_rfq(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    rfq = crud.rfq.get(db, id=id)
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    return rfq

@router.put("/{id}", response_model=schemas.RFQ)
def update_rfq(
    *,
    db: Session = Depends(get_db),
    id: str,
    rfq_in: schemas.RFQUpdate
) -> Any:
    rfq = crud.rfq.get(db, id=id)
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    return crud.rfq.update(db, db_obj=rfq, obj_in=rfq_in)

@router.delete("/{id}", response_model=schemas.RFQ)
def delete_rfq(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    rfq = crud.rfq.get(db, id=id)
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    return crud.rfq.remove(db, id=id)

# Snapshot Action
@router.post("/{id}/create-quote", response_model=schemas.Quote)
def create_quote_from_rfq(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    from app.services import snapshot
    return snapshot.create_quote_from_rfq(db, rfq_id=id)
