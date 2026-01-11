from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter()


@router.get("/", response_model=schemas.CustomerListResponse)
def read_customers(
    db: Session = Depends(get_db),
    page: int = 1,
    page_size: int = 100,
    status: str = None  # 'active', 'inactive', or None for all
) -> Any:
    """
    List customers with server-side pagination.
    Use status='active' or status='inactive' to filter.
    """
    skip = (page - 1) * page_size
    limit = page_size

    if status == "inactive":
        items = crud.customer.get_multi_inactive(db, skip=skip, limit=limit)
        total = crud.customer.count_inactive(db)
    elif status == "active":
        items = crud.customer.get_multi_active(db, skip=skip, limit=limit)
        total = crud.customer.count_active(db)
    else:
        # Default: active only (backward compatible)
        items = crud.customer.get_multi_active(db, skip=skip, limit=limit)
        total = crud.customer.count_active(db)

    return schemas.CustomerListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )



@router.post("/", response_model=schemas.Customer)
def create_customer(
    *,
    db: Session = Depends(get_db),
    customer_in: schemas.CustomerCreate
) -> Any:
    """Create a new customer. Status defaults to 'active'."""
    # Check for duplicate company_name
    existing = crud.customer.get_by_company_name(db, company_name=customer_in.company_name)
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Company name already exists"
        )
    customer = crud.customer.create(db, obj_in=customer_in)
    return customer


@router.get("/check-name")
def check_company_name(
    company_name: str,
    exclude_id: str = None,
    db: Session = Depends(get_db)
) -> Any:
    """
    Check if a company name already exists.
    Used for real-time validation on frontend blur event.
    """
    existing = crud.customer.get_by_company_name(db, company_name=company_name)
    if existing and (exclude_id is None or existing.id != exclude_id):
        return {"exists": True, "customer_id": existing.id}
    return {"exists": False}


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
    # Check for duplicate company_name if it's being changed
    if customer_in.company_name and customer_in.company_name != customer.company_name:
        existing = crud.customer.get_by_company_name(db, company_name=customer_in.company_name)
        if existing:
            raise HTTPException(
                status_code=409,
                detail="Company name already exists"
            )
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
