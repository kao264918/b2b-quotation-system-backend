from app.crud.base import CRUDBase
from app.models.template import QuoteTemplate, InvoiceTemplate
# Since template schemas are separated, we need separate CRUDs or use Any
from app.schemas.template import QuoteTemplate as QuoteTemplateSchema, InvoiceTemplate as InvoiceTemplateSchema

# For now just basic CRUD, templates are simpler
class CRUDQuoteTemplate(CRUDBase[QuoteTemplate, QuoteTemplateSchema, QuoteTemplateSchema]):
    pass

class CRUDInvoiceTemplate(CRUDBase[InvoiceTemplate, InvoiceTemplateSchema, InvoiceTemplateSchema]):
    pass

quote_template = CRUDQuoteTemplate(QuoteTemplate)
invoice_template = CRUDInvoiceTemplate(InvoiceTemplate)
