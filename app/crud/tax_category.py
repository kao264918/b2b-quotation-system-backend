from app.crud.base import CRUDBase
from app.models.tax_category import TaxCategory
from app.schemas.tax_category import TaxCategoryCreate, TaxCategoryUpdate

class CRUDTaxCategory(CRUDBase[TaxCategory, TaxCategoryCreate, TaxCategoryUpdate]):
    pass

tax_category = CRUDTaxCategory(TaxCategory)
