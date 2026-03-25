from math import ceil
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO

from app import crud, schemas
from app.database import get_db

router = APIRouter()


@router.get("", response_model=schemas.InvoiceListResponse)
def read_invoices(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    quote_id: str | None = None,
    search: str | None = None,
) -> Any:
    """Get all invoices (excluding soft-deleted)."""
    items, total = crud.invoice.get_multi(db, skip=skip, limit=limit, quote_id=quote_id, search=search)
    page_size = max(limit, 1)
    page = (skip // page_size) + 1
    total_pages = max(1, ceil(total / page_size)) if total else 1
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.post("", response_model=schemas.Invoice)
def create_invoice(
    *,
    db: Session = Depends(get_db),
    invoice_in: schemas.InvoiceCreate
) -> Any:
    """Create a new invoice."""
    return crud.invoice.create(db, obj_in=invoice_in)


@router.post("/from-quote", response_model=schemas.Invoice)
def create_invoice_from_quote(
    *,
    db: Session = Depends(get_db),
    request: schemas.InvoiceFromQuoteRequest
) -> Any:
    """
    Create invoice from a confirmed quote.
    Snapshots quote data into the invoice.
    """
    # Get the quote
    quote = crud.quote.get(db, id=request.quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="報價單不存在")
    
    if quote.status != "confirmed":
        raise HTTPException(
            status_code=400, 
            detail="只有已確認的報價單可以建立請款單"
        )
    
    try:
        invoice = crud.invoice.create_from_quote(db, quote=quote)
        return invoice
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{id}", response_model=schemas.Invoice)
def read_invoice(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    """Get invoice by ID."""
    invoice = crud.invoice.get(db, id=id)
    if not invoice:
        raise HTTPException(status_code=404, detail="請款單不存在")
    return invoice


@router.put("/{id}", response_model=schemas.Invoice)
def update_invoice(
    *,
    db: Session = Depends(get_db),
    id: str,
    invoice_in: schemas.InvoiceUpdate
) -> Any:
    """Update invoice fields."""
    invoice = crud.invoice.get(db, id=id)
    if not invoice:
        raise HTTPException(status_code=404, detail="請款單不存在")
    return crud.invoice.update(db, db_obj=invoice, obj_in=invoice_in)


@router.patch("/{id}/status", response_model=schemas.Invoice)
def update_invoice_status(
    *,
    db: Session = Depends(get_db),
    id: str,
    status_update: schemas.InvoiceStatusUpdate
) -> Any:
    """Update invoice status (draft → issued)."""
    invoice = crud.invoice.get(db, id=id)
    if not invoice:
        raise HTTPException(status_code=404, detail="請款單不存在")
    
    try:
        return crud.invoice.update_status(db, invoice=invoice, new_status=status_update.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{id}/accounting-status", response_model=schemas.Invoice)
def update_invoice_accounting_status(
    *,
    db: Session = Depends(get_db),
    id: str,
    status_update: schemas.InvoiceAccountingStatusUpdate
) -> Any:
    """Update invoice accounting status (unpaid/paid)."""
    invoice = crud.invoice.get(db, id=id)
    if not invoice:
        raise HTTPException(status_code=404, detail="請款單不存在")
    
    try:
        return crud.invoice.update_accounting_status(db, invoice=invoice, new_status=status_update.accounting_status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{id}/issue", response_model=schemas.Invoice)
def issue_invoice(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    """Issue a draft invoice."""
    invoice = crud.invoice.get(db, id=id)
    if not invoice:
        raise HTTPException(status_code=404, detail="請款單不存在")
    
    if invoice.status != "draft":
        raise HTTPException(status_code=400, detail="只有草稿狀態的請款單可以發出")
    
    try:
        return crud.invoice.update_status(db, invoice=invoice, new_status="issued")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{id}", response_model=schemas.Invoice)
def delete_invoice(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    """Soft delete an invoice."""
    invoice = crud.invoice.get(db, id=id)
    if not invoice:
        raise HTTPException(status_code=404, detail="請款單不存在")
    
    return crud.invoice.soft_delete(db, invoice=invoice)


@router.get("/{id}/export/pdf")
def export_invoice_pdf(
    *,
    db: Session = Depends(get_db),
    id: str
) -> StreamingResponse:
    """Export invoice as PDF."""
    invoice = crud.invoice.get(db, id=id)
    if not invoice:
        raise HTTPException(status_code=404, detail="請款單不存在")
    
    from app.services.invoice_export import generate_invoice_pdf
    
    pdf_bytes = generate_invoice_pdf(invoice)
    
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={invoice.invoice_number}.pdf"
        }
    )


@router.get("/{id}/export/excel")
def export_invoice_excel(
    *,
    db: Session = Depends(get_db),
    id: str
) -> StreamingResponse:
    """Export invoice as Excel."""
    invoice = crud.invoice.get(db, id=id)
    if not invoice:
        raise HTTPException(status_code=404, detail="請款單不存在")
    
    from app.services.invoice_export import generate_invoice_excel
    
    excel_bytes = generate_invoice_excel(invoice)
    
    return StreamingResponse(
        BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={invoice.invoice_number}.xlsx"
        }
    )
