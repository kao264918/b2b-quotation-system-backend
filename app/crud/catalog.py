from app.crud.base import CRUDBase
from app.models.catalog import CatalogItem
from app.schemas.catalog import CatalogItemCreate, CatalogItemUpdate

class CRUDCatalogItem(CRUDBase[CatalogItem, CatalogItemCreate, CatalogItemUpdate]):
    pass

catalog = CRUDCatalogItem(CatalogItem)
