from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter()

@router.get("", response_model=List[schemas.TaxCategory])
def read_tax_categories(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
) -> Any:
    return crud.tax_category.get_multi(db, skip=skip, limit=limit)

@router.post("", response_model=schemas.TaxCategory)
def create_tax_category(
    *,
    db: Session = Depends(get_db),
    category_in: schemas.TaxCategoryCreate
) -> Any:
    return crud.tax_category.create(db, obj_in=category_in)

@router.get("/{id}", response_model=schemas.TaxCategory)
def read_tax_category(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    category = crud.tax_category.get(db, id=id)
    if not category:
        raise HTTPException(status_code=404, detail="Tax Category not found")
    return category
