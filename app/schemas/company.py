"""
Company Schema - Unified view of Customer and Vendor entities

This provides a combined "company" view with role information
to support the /customers list showing all companies.
"""
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, ConfigDict


class CompanyListItem(BaseModel):
    """Unified company item for list display"""
    id: str
    company_name: str
    tax_id: Optional[str] = None
    contact_name: str
    contact_email: str
    status: str
    role: Literal["customer", "vendor", "both"]  # Role badge
    source: Literal["customer", "vendor"]  # Original source table
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class CompanyListResponse(BaseModel):
    """Paginated company list response"""
    items: List[CompanyListItem]
    total: int
    page: int
    page_size: int
    
    model_config = ConfigDict(from_attributes=True)
