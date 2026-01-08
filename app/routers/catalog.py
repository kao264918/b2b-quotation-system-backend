from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter()

@router.get("/", response_model=List[schemas.CatalogItem])
def read_catalog_items(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
) -> Any:
    return crud.catalog.get_multi(db, skip=skip, limit=limit)

@router.post("/", response_model=schemas.CatalogItem)
def create_catalog_item(
    *,
    db: Session = Depends(get_db),
    item_in: schemas.CatalogItemCreate
) -> Any:
    return crud.catalog.create(db, obj_in=item_in)

@router.get("/{id}", response_model=schemas.CatalogItem)
def read_catalog_item(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    item = crud.catalog.get(db, id=id)
    if not item:
        raise HTTPException(status_code=404, detail="Catalog Item not found")
    return item

@router.put("/{id}", response_model=schemas.CatalogItem)
def update_catalog_item(
    *,
    db: Session = Depends(get_db),
    id: str,
    item_in: schemas.CatalogItemUpdate
) -> Any:
    item = crud.catalog.get(db, id=id)
    if not item:
        raise HTTPException(status_code=404, detail="Catalog Item not found")
    return crud.catalog.update(db, db_obj=item, obj_in=item_in)

@router.delete("/{id}", response_model=schemas.CatalogItem)
def delete_catalog_item(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    item = crud.catalog.get(db, id=id)
    if not item:
        raise HTTPException(status_code=404, detail="Catalog Item not found")
    return crud.catalog.remove(db, id=id)
