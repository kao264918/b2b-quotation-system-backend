"""
Company Router - Unified view of Customer and Vendor entities

Provides a combined "company" listing that includes:
- All customers (role: "customer")
- All vendors (role: "vendor")
- With duplicate detection based on tax_id (role: "both")
"""
from typing import Any, Optional, List, Dict
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.customer import Customer
from app.models.vendor import Vendor
from app.schemas.company import CompanyListItem, CompanyListResponse

router = APIRouter()


@router.get("/", response_model=CompanyListResponse)
def list_companies(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=150),
    role: Optional[str] = Query(None, description="Filter by role: customer, vendor, or both"),
) -> Any:
    """
    List all companies (customers + vendors) with role badges.
    
    - role=customer: Only customers
    - role=vendor: Only vendors  
    - role=both: Companies that exist in both tables (matched by tax_id)
    - role=None: All companies
    """
    # Get all customers and vendors
    customers = db.query(Customer).filter(Customer.status == "active").all()
    vendors = db.query(Vendor).filter(Vendor.status == "active").all()
    
    # Build tax_id index for "both" detection
    customer_tax_ids: Dict[str, Customer] = {}
    for c in customers:
        if c.tax_id:
            customer_tax_ids[c.tax_id] = c
    
    vendor_tax_ids: Dict[str, Vendor] = {}
    for v in vendors:
        if v.tax_id:
            vendor_tax_ids[v.tax_id] = v
    
    # Detect overlapping tax_ids
    both_tax_ids = set(customer_tax_ids.keys()) & set(vendor_tax_ids.keys())
    
    # Build unified company list
    items: List[CompanyListItem] = []
    seen_tax_ids = set()
    
    # Process customers
    for c in customers:
        is_both = c.tax_id and c.tax_id in both_tax_ids
        company_role = "both" if is_both else "customer"
        
        if role and role != company_role:
            continue
            
        items.append(CompanyListItem(
            id=c.id,
            company_name=c.company_name,
            tax_id=c.tax_id,
            contact_name=c.contact_name,
            contact_email=c.contact_email,
            status=c.status,
            role=company_role,
            source="customer",
            created_at=c.created_at,
            updated_at=c.updated_at,
        ))
        
        if c.tax_id:
            seen_tax_ids.add(c.tax_id)
    
    # Process vendors (skip if already added via customer with same tax_id)
    for v in vendors:
        is_both = v.tax_id and v.tax_id in both_tax_ids
        
        # Skip if this vendor's tax_id was already added from customer side
        if v.tax_id and v.tax_id in seen_tax_ids:
            continue
            
        company_role = "both" if is_both else "vendor"
        
        if role and role != company_role:
            continue
        
        # Get primary contact info
        primary_contact_name = v.name  # Fallback to vendor name
        primary_contact_email = v.email or ""
        
        if v.contacts:
            for contact in v.contacts:
                if contact.is_primary:
                    primary_contact_name = contact.name
                    primary_contact_email = contact.email or v.email or ""
                    break
            # If no primary, use first contact
            if not primary_contact_email and v.contacts:
                first_contact = v.contacts[0]
                primary_contact_name = first_contact.name
                primary_contact_email = first_contact.email or v.email or ""
        
        items.append(CompanyListItem(
            id=v.id,
            company_name=v.company_name,
            tax_id=v.tax_id,
            contact_name=primary_contact_name,
            contact_email=primary_contact_email,
            status=v.status,
            role=company_role,
            source="vendor",
            created_at=v.created_at,
            updated_at=v.updated_at,
        ))
    
    # Sort by company_name
    items.sort(key=lambda x: x.company_name)
    
    # Apply pagination
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_items = items[start:end]
    
    return CompanyListResponse(
        items=paginated_items,
        total=total,
        page=page,
        page_size=page_size,
    )
