from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter()

@router.get("/", response_model=List[schemas.Customer])
def read_customers(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
) -> Any:
    customers = crud.customer.get_multi(db, skip=skip, limit=limit)
    return customers

@router.post("/", response_model=schemas.Customer)
def create_customer(
    *,
    db: Session = Depends(get_db),
    customer_in: schemas.CustomerCreate
) -> Any:
    customer = crud.customer.create(db, obj_in=customer_in)
    return customer

@router.get("/{id}", response_model=schemas.Customer)
def read_customer(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    customer = crud.customer.get(db, id=id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

@router.put("/{id}", response_model=schemas.Customer)
def update_customer(
    *,
    db: Session = Depends(get_db),
    id: str,
    customer_in: schemas.CustomerUpdate
) -> Any:
    customer = crud.customer.get(db, id=id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    customer = crud.customer.update(db, db_obj=customer, obj_in=customer_in)
    return customer

@router.delete("/{id}", response_model=schemas.Customer)
def delete_customer(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    customer = crud.customer.get(db, id=id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    customer = crud.customer.remove(db, id=id) # Type mismatch possible if ID is str vs int, generic was int. 
    # Fix generic or casting? CRUDBase generic for ID was any? remove expects `id: int`. 
    # I should check CRUDBase implementation. It typed id as int.
    # I will need to override or fix CRUDBase for string IDs.
    # CUSTOMER UUID is string. 
    return customer
