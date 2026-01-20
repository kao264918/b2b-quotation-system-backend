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

router = APIRouter()


@router.post("/", response_model=RFQResponse, status_code=201)
def create_rfq(
    *,
    db: Session = Depends(get_db),
    rfq_in: RFQCreate
) -> Any:
    """Create a new RFQ with initial version."""
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
            vendor_name=rfq.vendor.name if rfq.vendor else "Unknown",
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
