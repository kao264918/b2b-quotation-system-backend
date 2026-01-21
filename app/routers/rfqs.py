"""
RFQ API Router (Versioned)

Endpoints:
- POST   /api/v1/rfqs                           Create RFQ (with v1)
- GET    /api/v1/rfqs                           List RFQs (paginated)
- GET    /api/v1/rfqs/{id}                      Get RFQ detail
- PUT    /api/v1/rfqs/{id}                      Update RFQ (creates new version)
- DELETE /api/v1/rfqs/{id}                      Delete RFQ
- PATCH  /api/v1/rfqs/{id}/status               Update status only
- GET    /api/v1/rfqs/{id}/versions             List versions
- GET    /api/v1/rfqs/{id}/versions/{vid}       Get specific version
- POST   /api/v1/rfqs/{id}/versions/{vid}/select  Select final version
"""
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import math

from app.database import get_db
from app.schemas.rfq import (
    RFQCreate, RFQUpdate, RFQStatusUpdate, RFQAccountingStatusUpdate,
    RFQResponse, RFQDetailResponse, RFQListItemResponse, RFQListResponse,
    RFQVersionResponse, RFQVersionSummary, RFQSelectVersion
)
from app.crud import rfq as rfq_crud
from app.services import export_service
from fastapi.responses import StreamingResponse

router = APIRouter()


def validate_output_dims(items) -> list[dict]:
    """
    Validate that output-type items have both length_cm and width_cm.
    Returns list of field-level errors for frontend bottom message mapping.
    """
    errors = []
    for idx, item in enumerate(items):
        item_dict = item.model_dump() if hasattr(item, 'model_dump') else item
        if item_dict.get('item_type') == 'output':
            # Check length/width presence (allow 0 if specific use case, but usually must be > 0. prompt says "missing", so falsy check is usually ok but 0 dim is weird)
            # Pydantic schema allows 0 (ge=0).
            # Requirement says "Missing".
            # If 0 is valid, we should check for None. But usually dims cannot be 0.
            # Let's check for None first. if 0 is passed, it is truthy False.
            # Assuming dims > 0 is required.
            l = item_dict.get('length_cm')
            w = item_dict.get('width_cm')
            if l is None or w is None or l == 0 or w == 0:
                errors.append({
                    "field": f"items[{idx}].dimensions",
                    "item_id": item_dict.get('id'), # Return FE ID if provided
                    "message": "輸出類型項目必須填寫長度與寬度",
                    "item_name": item_dict.get('name', f'Item {idx+1}')
                })
    return errors


@router.post("/", response_model=RFQResponse, status_code=201)
def create_rfq(
    *,
    db: Session = Depends(get_db),
    rfq_in: RFQCreate
) -> Any:
    """Create a new RFQ with initial version."""
    # B2: Validate output dims
    dim_errors = validate_output_dims(rfq_in.items)
    if dim_errors:
        raise HTTPException(
            status_code=400, 
            detail={"message": "輸出類型項目缺少尺寸資料", "errors": dim_errors}
        )
    
    try:
        rfq = rfq_crud.create_rfq(db, obj_in=rfq_in)
        return rfq
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=RFQListResponse)
def list_rfqs(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=150),
    search: Optional[str] = None,
    status: Optional[str] = None
) -> Any:
    """List RFQs with pagination and search."""
    skip = (page - 1) * page_size
    
    rfqs = rfq_crud.get_rfqs(db, skip=skip, limit=page_size, search=search, status=status)
    total = rfq_crud.count_rfqs(db, search=search, status=status)
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    
    # Map to list response
    items = []
    for rfq in rfqs:
        # Get current version totals
        current_version = None
        for v in rfq.versions:
            if v.id == rfq.current_version_id:
                current_version = v
                break
        
        items.append(RFQListItemResponse(
            id=rfq.id,
            rfq_no=rfq.rfq_no,
            project_name=rfq.project_name,
            vendor_name=rfq.vendor.company_name if rfq.vendor else "Unknown",
            status=rfq.status,
            accounting_status=rfq.accounting_status,
            subtotal=current_version.subtotal if current_version else 0,
            total_amount=current_version.total_amount if current_version else 0,
            created_at=rfq.created_at,
            updated_at=rfq.updated_at,
        ))
    
    return RFQListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{id}", response_model=RFQDetailResponse)
def get_rfq(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    """Get RFQ detail with current version."""
    rfq = rfq_crud.get_rfq(db, rfq_id=id)
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    
    # Get current version
    current_version = None
    for v in rfq.versions:
        if v.id == rfq.current_version_id:
            current_version = v
            break
    
    # Build version summaries
    version_summaries = [
        RFQVersionSummary(
            id=v.id,
            version_number=v.version_number,
            total_amount=v.total_amount,
            created_at=v.created_at,
            notes=v.notes
        )
        for v in sorted(rfq.versions, key=lambda x: x.version_number, reverse=True)
    ]
    
    return RFQDetailResponse(
        id=rfq.id,
        rfq_no=rfq.rfq_no,
        project_name=rfq.project_name,
        vendor_id=rfq.vendor_id,
        status=rfq.status,
        accounting_status=rfq.accounting_status,
        current_version_id=rfq.current_version_id,
        selected_version_id=rfq.selected_version_id,
        created_at=rfq.created_at,
        updated_at=rfq.updated_at,
        current_version=current_version,
        versions=version_summaries,
    )


@router.put("/{id}", response_model=RFQDetailResponse)
def update_rfq(
    *,
    db: Session = Depends(get_db),
    id: str,
    rfq_in: RFQUpdate
) -> Any:
    """Update RFQ by creating a new version."""
    rfq = rfq_crud.get_rfq(db, rfq_id=id)
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    
    # Check if RFQ is in a locked status
    if rfq.status in ["finalized", "closed", "discarded"]:
        raise HTTPException(status_code=400, detail="Cannot modify a locked RFQ. Use Revert to re-open.")
    
    # B2: Validate output dims if items provided
    if rfq_in.items:
        dim_errors = validate_output_dims(rfq_in.items)
        if dim_errors:
            raise HTTPException(
                status_code=400, 
                detail={"message": "輸出類型項目缺少尺寸資料", "errors": dim_errors}
            )
    
    try:
        rfq_crud.create_new_version(db, rfq=rfq, obj_in=rfq_in)
        # Refresh and return
        rfq = rfq_crud.get_rfq(db, rfq_id=id)
        return get_rfq(db=db, id=id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{id}", status_code=204)
def delete_rfq(
    *,
    db: Session = Depends(get_db),
    id: str
) -> None:
    """Delete RFQ and all versions. Only allowed in DRAFT or VENDOR_QUOTING status."""
    try:
        if not rfq_crud.delete_rfq(db, rfq_id=id):
            raise HTTPException(status_code=404, detail="RFQ not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{id}/status", response_model=RFQResponse)
def update_rfq_status(
    *,
    db: Session = Depends(get_db),
    id: str,
    status_in: RFQStatusUpdate
) -> Any:
    """Update RFQ workflow status."""
    rfq = rfq_crud.get_rfq(db, rfq_id=id)
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    
    return rfq_crud.update_status(db, rfq=rfq, status=status_in.status)


@router.get("/{id}/versions", response_model=List[RFQVersionSummary])
def list_versions(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    """List all versions for an RFQ."""
    versions = rfq_crud.get_versions(db, rfq_id=id)
    return [
        RFQVersionSummary(
            id=v.id,
            version_number=v.version_number,
            total_amount=v.total_amount,
            created_at=v.created_at,
            notes=v.notes
        )
        for v in versions
    ]


@router.get("/{id}/versions/{version_id}", response_model=RFQVersionResponse)
def get_version(
    *,
    db: Session = Depends(get_db),
    id: str,
    version_id: str
) -> Any:
    """Get specific version details."""
    version = rfq_crud.get_version(db, version_id=version_id)
    if not version or version.rfq_id != id:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


@router.post("/{id}/versions/{version_id}/select", response_model=RFQResponse)
def select_final_version(
    *,
    db: Session = Depends(get_db),
    id: str,
    version_id: str
) -> Any:
    """Select a version as the final version. Sets RFQ status to FINALIZED."""
    rfq = rfq_crud.get_rfq(db, rfq_id=id)
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    
    try:
        return rfq_crud.select_final_version(db, rfq=rfq, version_id=version_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{id}/revert", response_model=RFQVersionResponse)
def revert_rfq(
    *,
    db: Session = Depends(get_db),
    id: str
) -> Any:
    """
    Revert a FINALIZED RFQ to VENDOR_QUOTING.
    Creates a new version from the final version.
    """
    rfq = rfq_crud.get_rfq(db, rfq_id=id)
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    
    try:
        return rfq_crud.revert_rfq(db, rfq=rfq)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{id}/accounting-status", response_model=RFQResponse)
def update_accounting_status(
    *,
    db: Session = Depends(get_db),
    id: str,
    status_in: RFQAccountingStatusUpdate
) -> Any:
    """Update accounting status (independent of workflow status)."""
    rfq = rfq_crud.get_rfq(db, rfq_id=id)
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    
    return rfq_crud.update_accounting_status(db, rfq=rfq, accounting_status=status_in.accounting_status)


@router.get("/{id}/export/pdf")
def export_rfq_pdf(
    *,
    db: Session = Depends(get_db),
    id: str
):
    """Export RFQ to PDF (Latest/Selected Version)."""
    rfq = rfq_crud.get_rfq(db, rfq_id=id)
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    
    # Determine version: Selected > Current
    target_version_id = rfq.selected_version_id or rfq.current_version_id
    if not target_version_id:
         raise HTTPException(status_code=404, detail="No active version found for RFQ")
         
    version = rfq_crud.get_version(db, version_id=target_version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    pdf_buffer = export_service.generate_pdf(rfq, version)
    
    filename = f"{rfq.rfq_no}-v{version.version_number}.pdf"
    
    from urllib.parse import quote
    
    encoded_filename = quote(filename)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        "Access-Control-Expose-Headers": "Content-Disposition"
    }
    
    return StreamingResponse(
        pdf_buffer, 
        media_type="application/pdf",
        headers=headers
    )


@router.get("/{id}/export/excel")
def export_rfq_excel(
    *,
    db: Session = Depends(get_db),
    id: str
):
    """Export RFQ to Excel (Latest/Selected Version)."""
    rfq = rfq_crud.get_rfq(db, rfq_id=id)
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    
    target_version_id = rfq.selected_version_id or rfq.current_version_id
    if not target_version_id:
         raise HTTPException(status_code=404, detail="No active version found for RFQ")
         
    version = rfq_crud.get_version(db, version_id=target_version_id)
    if not version:
         raise HTTPException(status_code=404, detail="Version not found")

    excel_buffer = export_service.generate_excel(rfq, version)
    
    filename = f"{rfq.rfq_no}-v{version.version_number}.xlsx"
    
    encoded_filename = quote(filename)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        "Access-Control-Expose-Headers": "Content-Disposition"
    }
    
    return StreamingResponse(
        excel_buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )
