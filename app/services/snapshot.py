from sqlalchemy.orm import Session
from app import crud, models, schemas
from app.services import calculation
from fastapi import HTTPException
from decimal import Decimal

def create_quote_from_rfq(db: Session, rfq_id: str) -> models.Quote:
    rfq = crud.rfq.get(db, id=rfq_id)
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
        
    # Validation: Check if all items have selling price?
    # For now, allow 0 if missing, or enforce. 
    # Logic: Unit Price = selling_price.
    
    quote_items_in = []
    
    subtotal_accum = Decimal(0)
    tax_accum = Decimal(0)
    total_accum = Decimal(0)
    
    for rfq_item in rfq.items:
        # 1. 取得售價 (若無則預設 0 或報錯)
        unit_price = rfq_item.selling_price or Decimal(0)
        
        # 2. 取得稅率 (需查詢 TaxCategory)
        # 這裡為了簡化，假設 tax_category 是 code 或 id。需查詢 DB 取得 rate。
        # 假設 rfq_item.tax_category 存的是 ID (uuid) 或 Code?
        # Model definition: `tax_category: Mapped[str | None]`
        # 實務上應查表。這裡先實作查找邏輯。
        tax_rate = Decimal(0)
        tax_cat_name = "N/A"
        
        if rfq_item.tax_category:
            # 嘗試用 ID 查，或 Code 查
            # 這裡假設存的是 ID (因為前端通常選 ID)
            tax_cat = crud.tax_category.get(db, id=rfq_item.tax_category)
            # 如果不是 ID，試試看是否為 Code? (略，假設 ID)
            if tax_cat:
                tax_rate = tax_cat.rate
                tax_cat_name = tax_cat.name
        
        # 3. 計算
        calc = calculation.calculate_line_item(
            quantity=rfq_item.quantity,
            unit_price=unit_price,
            tax_rate=tax_rate
        )
        
        # 4. 準備 QuoteItem
        item_in = schemas.QuoteItemCreate(
            name=rfq_item.name,
            description=rfq_item.description,
            quantity=rfq_item.quantity,
            unit=rfq_item.unit,
            unit_price=unit_price,
            
            tax_category_name=tax_cat_name,
            tax_rate=tax_rate,
            
            subtotal=calc["subtotal"],
            tax_amount=calc["tax_amount"],
            total_amount=calc["total_amount"],
            
            # Deprecated field
            line_total=calc["total_amount"],
            
            rfq_item_id=rfq_item.id,
            catalog_item_id=rfq_item.catalog_item_id
        )
        
        quote_items_in.append(item_in)
        
        subtotal_accum += calc["subtotal"]
        tax_accum += calc["tax_amount"]
        total_accum += calc["total_amount"]
        
    # Create Quote
    quote_in = schemas.QuoteCreate(
        title=f"Quote for {rfq.title}",
        rfq_id=rfq.id,
        customer_id=rfq.customer_id,
        status="draft",
        items=quote_items_in,
        subtotal=subtotal_accum,
        tax_total=tax_accum,
        total=total_accum
    )
    
    return crud.quote.create(db, obj_in=quote_in)

def create_invoice_from_quote(db: Session, quote_id: str) -> models.Invoice:
    quote = crud.quote.get(db, id=quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    invoice_items_in = []
    
    for q_item in quote.items:
        # Snapshot copy logic (Copy exactly)
        item_in = schemas.InvoiceItemCreate(
            name=q_item.name,
            description=q_item.description,
            quantity=q_item.quantity,
            unit=q_item.unit,
            unit_price=q_item.unit_price,
            
            tax_category_name=q_item.tax_category_name,
            tax_rate=q_item.tax_rate,
            
            subtotal=q_item.subtotal,
            tax_amount=q_item.tax_amount,
            total_amount=q_item.total_amount,
            
            line_total=q_item.line_total,
            
            quote_item_id=q_item.id
        )
        invoice_items_in.append(item_in)
        
    invoice_in = schemas.InvoiceCreate(
        quote_id=quote.id,
        customer_id=quote.customer_id,
        status="draft",
        items=invoice_items_in,
        
        subtotal=quote.subtotal,
        tax_total=quote.tax_total,
        total=quote.total
    )
    
    return crud.invoice.create(db, obj_in=invoice_in)
