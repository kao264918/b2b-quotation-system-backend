from typing import Any, List, Literal
import io
import math

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import crud, schemas
from app.crud.quote import QuoteValidationError
from app.database import get_db
from app.deps.auth import get_current_user
from app.models.user import User
from app.services.promotion_pricing import PromotionValidationError, get_promotion_runtime_status, validate_promotion_for_quote

router = APIRouter()


def can_view_internal_cost(user: User) -> bool:
    return True


def _serialize_quote_for_user(quote: Any, current_user: User) -> dict:
    data = schemas.Quote.model_validate(quote).model_dump()
    if quote.status == "draft":
        if getattr(quote, "promotion_id", None) and getattr(quote, "promotion", None):
            invalid_code = None
            invalid_message = None
            is_eligible = True
            try:
                validate_promotion_for_quote(
                    quote._sa_instance_state.session,
                    quote.promotion,
                    quote.items,
                    quote.subtotal,
                )
            except PromotionValidationError as exc:
                is_eligible = False
                invalid_code = exc.code
                invalid_message = exc.message
            data["applied_promotion"] = {
                "id": quote.promotion.id,
                "code": quote.promotion.promotion_code,
                "name": quote.promotion.promotion_name,
                "type": quote.promotion.type,
                "value": quote.promotion.discount_value,
                "scope": quote.promotion.scope,
                "scope_category": quote.promotion.scope_category,
                "discount_amount": quote.promotion_discount_amount,
                "runtime_status": get_promotion_runtime_status(quote.promotion),
                "is_eligible": is_eligible,
                "invalid_code": invalid_code,
                "invalid_message": invalid_message,
                "source": "live",
            }
    elif getattr(quote, "promotion_discount_amount", None):
        data["applied_promotion"] = {
            "id": quote.promotion_id,
            "code": quote.promotion_code_snapshot,
            "name": quote.promotion_name_snapshot,
            "type": quote.promotion_type_snapshot,
            "value": quote.promotion_value_snapshot,
            "scope": quote.promotion_scope_snapshot,
            "scope_category": quote.promotion_scope_category_snapshot,
            "discount_amount": quote.promotion_discount_amount,
            "source": "snapshot",
        }
    if can_view_internal_cost(current_user):
        return data

    data["total_cost"] = None
    data["gross_profit_amount"] = None
    data["gross_profit_rate"] = None
    for item in data.get("items", []):
        item["snapshot_cost"] = None
    return data


@router.get("", response_model=schemas.QuoteListResponse)
def read_quotes(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    sort_by: str | None = None,
    sort_order: Literal["asc", "desc"] = "desc",
    current_user: User = Depends(get_current_user),
) -> Any:
    quotes = crud.quote.get_multi(
        db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    total = crud.quote.count_multi(db)
    page = (skip // limit) + 1 if limit > 0 else 1
    total_pages = math.ceil(total / limit) if limit > 0 and total > 0 else 1
    return schemas.QuoteListResponse(
        items=[_serialize_quote_for_user(quote, current_user) for quote in quotes],
        total=total,
        page=page,
        page_size=limit,
        total_pages=total_pages,
    )


@router.post("", response_model=schemas.Quote)
def create_quote(
    *,
    db: Session = Depends(get_db),
    quote_in: schemas.QuoteCreate,
    current_user: User = Depends(get_current_user),
) -> Any:
    try:
        quote = crud.quote.create(db, obj_in=quote_in)
        return _serialize_quote_for_user(quote, current_user)
    except QuoteValidationError as e:
        raise HTTPException(status_code=400, detail=e.to_detail())


@router.get("/internal-kpi", response_model=schemas.QuoteInternalKPI)
def get_internal_quote_kpi(
    *,
    db: Session = Depends(get_db),
    range: Literal["month", "quarter", "all"] = "month",
    current_user: User = Depends(get_current_user),
) -> Any:
    if not can_view_internal_cost(current_user):
        raise HTTPException(status_code=403, detail="Permission denied")
    return crud.quote.get_internal_kpi(db, range_type=range)


@router.get("/{id}", response_model=schemas.Quote)
def read_quote(
    *,
    db: Session = Depends(get_db),
    id: str,
    current_user: User = Depends(get_current_user),
) -> Any:
    quote = crud.quote.get(db, id=id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return _serialize_quote_for_user(quote, current_user)


@router.put("/{id}", response_model=schemas.Quote)
def update_quote(
    *,
    db: Session = Depends(get_db),
    id: str,
    quote_in: schemas.QuoteUpdate,
    current_user: User = Depends(get_current_user),
) -> Any:
    quote = crud.quote.get(db, id=id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    try:
        updated = crud.quote.update_with_items(db, quote=quote, obj_in=quote_in)
        return _serialize_quote_for_user(updated, current_user)
    except QuoteValidationError as e:
        raise HTTPException(status_code=400, detail=e.to_detail())
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
    status_in: schemas.QuoteStatusUpdate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update quotation status (draft → confirmed → closed/discarded)."""
    quote = crud.quote.get(db, id=id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    try:
        updated = crud.quote.update_status(db, quote=quote, new_status=status_in.status)
        return _serialize_quote_for_user(updated, current_user)
    except QuoteValidationError as e:
        raise HTTPException(status_code=400, detail=e.to_detail())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{id}/accounting-status", response_model=schemas.Quote)
def update_quote_accounting_status(
    *,
    db: Session = Depends(get_db),
    id: str,
    status_in: schemas.QuoteAccountingStatusUpdate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update accounting status (unpaid/paid). Only for confirmed/closed/discarded quotes."""
    quote = crud.quote.get(db, id=id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    try:
        updated = crud.quote.update_accounting_status(db, quote=quote, new_status=status_in.accounting_status)
        return _serialize_quote_for_user(updated, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{id}/revert", response_model=schemas.Quote)
def revert_quote(
    *,
    db: Session = Depends(get_db),
    id: str,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Revert a closed/discarded quote back to confirmed, creating a new version."""
    quote = crud.quote.get(db, id=id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    try:
        updated = crud.quote.revert_quote(db, quote=quote)
        return _serialize_quote_for_user(updated, current_user)
    except QuoteValidationError as e:
        raise HTTPException(status_code=400, detail=e.to_detail())
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
