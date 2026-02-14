from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import io

from app import crud, schemas
from app.database import get_db

router = APIRouter()

@router.get("", response_model=List[schemas.Quote])
def read_quotes(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
) -> Any:
    return crud.quote.get_multi(db, skip=skip, limit=limit)

@router.post("", response_model=schemas.Quote)
def create_quote(
    *,
    db: Session = Depends(get_db),
    quote_in: schemas.QuoteCreate
) -> Any:
    return crud.quote.create(db, obj_in=quote_in)

@router.get("/{id}", response_model=schemas.Quote)
def read_quote(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    quote = crud.quote.get(db, id=id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return quote

@router.put("/{id}", response_model=schemas.Quote)
def update_quote(
    *,
    db: Session = Depends(get_db),
    id: str,
    quote_in: schemas.QuoteUpdate
) -> Any:
    quote = crud.quote.get(db, id=id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    try:
        return crud.quote.update_with_items(db, quote=quote, obj_in=quote_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{id}")
def delete_quote(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    quote = crud.quote.get(db, id=id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    crud.quote.remove(db, id=id)
    return {"status": "deleted"}

# Status Actions
@router.patch("/{id}/status", response_model=schemas.Quote)
def update_quote_status(
    *,
    db: Session = Depends(get_db),
    id: str,
    status_in: schemas.QuoteStatusUpdate
) -> Any:
    """Update quotation status (draft → confirmed → closed/discarded)."""
    quote = crud.quote.get(db, id=id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    try:
        return crud.quote.update_status(db, quote=quote, new_status=status_in.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{id}/accounting-status", response_model=schemas.Quote)
def update_quote_accounting_status(
    *,
    db: Session = Depends(get_db),
    id: str,
    status_in: schemas.QuoteAccountingStatusUpdate
) -> Any:
    """Update accounting status (unpaid/paid). Only for confirmed/closed/discarded quotes."""
    quote = crud.quote.get(db, id=id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    try:
        return crud.quote.update_accounting_status(db, quote=quote, new_status=status_in.accounting_status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{id}/revert", response_model=schemas.Quote)
def revert_quote(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    """Revert a closed/discarded quote back to confirmed, creating a new version."""
    quote = crud.quote.get(db, id=id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    try:
        return crud.quote.revert_quote(db, quote=quote)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Audit Logs
@router.get("/{id}/audit-logs", response_model=List[schemas.QuoteAuditLog])
def get_quote_audit_logs(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    """Get audit trail for a quote."""
    quote = crud.quote.get(db, id=id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    logs = crud.quote.get_audit_logs(db, quote_id=id)
    # Map to response schema
    return [
        {
            "id": log.id,
            "action": log.action,
            "category": log.changes.get("category", log.action) if log.changes else log.action,
            "timestamp": log.timestamp,
            "actor": log.actor,
            "changes": log.changes
        }
        for log in logs
    ]

# Export Endpoints
@router.get("/{id}/export/pdf")
def export_quote_pdf(
    *,
    db: Session = Depends(get_db),
    id: str,
    version: int = None
) -> Any:
    """Export quote as PDF."""
    quote = crud.quote.get(db, id=id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    # Generate PDF (placeholder - using simple text for now)
    # In production, use a proper PDF generator like reportlab or weasyprint
    from app.services.quote_export import generate_quote_pdf
    
    try:
        pdf_bytes = generate_quote_pdf(quote, version)
        filename = f"{quote.quote_number}-v{version or quote.version}.pdf"
        
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")

@router.get("/{id}/export/excel")
def export_quote_excel(
    *,
    db: Session = Depends(get_db),
    id: str,
    version: int = None
) -> Any:
    """Export quote as Excel."""
    quote = crud.quote.get(db, id=id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    from app.services.quote_export import generate_quote_excel
    
    try:
        excel_bytes = generate_quote_excel(quote, version)
        filename = f"{quote.quote_number}-v{version or quote.version}.xlsx"
        
        return StreamingResponse(
            io.BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate Excel: {str(e)}")

# Legacy endpoint - kept for backward compatibility
@router.post("/{id}/create-invoice", response_model=schemas.Invoice)
def create_invoice_from_quote(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    from app.services import snapshot
    return snapshot.create_invoice_from_quote(db, quote_id=id)

