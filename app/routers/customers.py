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
    limit: int = 100,
    include_inactive: bool = False
) -> Any:
    """
    List customers.
    By default, only returns active customers per CUSTOMER_FIELD_SPEC.md.
    Use include_inactive=true to get all customers (admin use).
    """
    if include_inactive:
        customers = crud.customer.get_multi(db, skip=skip, limit=limit)
    else:
        customers = crud.customer.get_multi_active(db, skip=skip, limit=limit)
    return customers


@router.post("/", response_model=schemas.Customer)
def create_customer(
    *,
    db: Session = Depends(get_db),
    customer_in: schemas.CustomerCreate
) -> Any:
    """Create a new customer. Status defaults to 'active'."""
    customer = crud.customer.create(db, obj_in=customer_in)
    return customer


@router.get("/{id}", response_model=schemas.Customer)
def read_customer(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    """Get customer by ID. Returns full customer object."""
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
    """Update customer. Returns full updated customer object."""
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
    """
    Soft delete customer (set status to inactive).
    Per CUSTOMER_FIELD_SPEC.md: Customer records MUST NOT be hard-deleted.
    """
    customer = crud.customer.get(db, id=id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    customer = crud.customer.soft_delete(db, id=id)
    return customer
