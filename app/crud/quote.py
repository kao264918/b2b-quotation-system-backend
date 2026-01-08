from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models.quote import Quote, QuoteItem
from app.schemas.quote import QuoteCreate, QuoteUpdate

class CRUDQuote(CRUDBase[Quote, QuoteCreate, QuoteUpdate]):
    def create(self, db: Session, *, obj_in: QuoteCreate) -> Quote:
        obj_data = obj_in.model_dump()
        items_data = obj_data.pop("items", [])
        
        db_obj = Quote(**obj_data)
        db.add(db_obj)
        db.flush()
        
        for item in items_data:
            db_item = QuoteItem(**item, quote_id=db_obj.id)
            db.add(db_item)
            
        db.commit()
        db.refresh(db_obj)
        return db_obj

quote = CRUDQuote(Quote)
