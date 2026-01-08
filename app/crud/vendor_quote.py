from app.crud.base import CRUDBase
from app.models.vendor_quote import VendorQuote
from app.schemas.vendor_quote import VendorQuoteCreate, VendorQuoteUpdate

class CRUDVendorQuote(CRUDBase[VendorQuote, VendorQuoteCreate, VendorQuoteUpdate]):
    pass

vendor_quote = CRUDVendorQuote(VendorQuote)
