import sys
import os
import requests
import json
import time

BASE_URL = "http://localhost:8000/api/v1"

def log(msg, status="INFO"):
    print(f"[{status}] {msg}")

# Add parent directory to path to allow importing app
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal
from app.models.user import User
from app.models.user_status import UserStatus, UserRole
from app.crud.user import user as crud_user

def setup_and_login(session):
    """
    Ensures a test admin user exists and logs in.
    """
    email = "integration_test_admin@example.com"
    password = "password123"
    
    db = SessionLocal()
    try:
        user = crud_user.get_by_email(db, email=email)
        if not user:
            log(f"Creating test admin user: {email}")
            user = User(
                email=email,
                hashed_password=crud_user.get_password_hash(password),
                full_name="Integration Test Admin",
                is_active=True,
                is_superuser=True,
                is_verified=True,
                status=UserStatus.ACTIVE,
                role=UserRole.OWNER
            )
            db.add(user)
            db.commit()
        else:
             # Ensure active/admin
             if not user.is_active or not user.is_superuser:
                 user.is_active = True
                 user.is_superuser = True
                 user.status = UserStatus.ACTIVE
                 user.role = UserRole.OWNER
                 db.commit()
    except Exception as e:
        log(f"DB Error during setup: {e}", "CRITICAL")
        return False
    finally:
        db.close()

    # Login
    login_data = {
        "email": email,
        "password": password,
        "remember_me": False
    }
    
    resp = session.post(f"{BASE_URL}/auth/login", json=login_data)
    if resp.status_code == 200:
        log(f"Login Successful as {email}")
        return True
    else:
        log(f"Login Failed: {resp.status_code} {resp.text}", "CRITICAL")
        return False

def test_customer_flow(session):
    log("--- Testing Customer Flow ---")
    
    # 1. Create Customer
    suffix = int(time.time())
    customer_data = {
        "company_name": f"Test Integration Corp {suffix}",
        "tax_id": f"876{suffix % 100000:05d}",
        "contact_name": "Test User",
        "contact_email": f"test_{suffix}@integration.com",
        "contact_phone": "0912345678",
        "address_line1": "123 Test St",
        "city": "Test City",
        "country": "TW"
    }
    
    resp = session.post(f"{BASE_URL}/customers/", json=customer_data)
    if resp.status_code != 200:
        log(f"Create Customer Failed: {resp.text}", "ERROR")
        return None
    
    customer = resp.json()
    log(f"Created Customer: {customer['id']}")
    
    # Verify role
    if "customer" not in customer.get("roles", []):
         log(f"Customer Role Verification Failed: {customer.get('roles')}", "ERROR")
    else:
         log("Customer Role Assignment Verified")

    # 2. Get Customer List
    resp = session.get(f"{BASE_URL}/customers/?page=1&page_size=10")
    if resp.status_code != 200:
        log("Get Customers Failed", "ERROR")
    else:
        log(f"Fetched Customer List: Found {len(resp.json()['items'])} items")

    return customer['id']




def test_vendor_flow(session=None):
    log("--- Testing Vendor Flow (via Unified Customer API) ---")
    
    s = session if session else requests.Session()
    if not session:
        # Get CSRF if new session
        csrf_resp = s.get(f"{BASE_URL}/auth/csrf")
        if csrf_resp.status_code == 200:
            s.headers.update({"x-csrf-token": csrf_resp.json().get("csrf_token")})

    suffix = int(time.time())
    # Create vendor using Customer API with roles
    vendor_data = {
        "company_name": f"Test Vendor Corp {suffix}",
        "tax_id": f"123{suffix % 100000:05d}",
        "contact_name": f"Test Vendor {suffix}",
        "contact_email": f"vendor_{suffix}@test.com",
        "contact_phone": "0912345678",
        "address_line1": "Vendor Address",
        "city": "Taipei",
        "country": "TW",
        "status": "active",
        "roles": ["vendor"]
    }
    
    resp = s.post(f"{BASE_URL}/customers/", json=vendor_data)
    if resp.status_code != 200:
        # Check if 200 or 201
        log(f"Create Vendor (Customer) Failed: {resp.status_code} {resp.text}", "ERROR")
        return None
        
    vendor = resp.json()
    log(f"Created Vendor (as Customer): {vendor['id']}")
    
    # Verify role
    if "vendor" not in vendor.get("roles", []):
         log(f"Vendor Role Verification Failed: {vendor.get('roles')}", "ERROR")
    else:
         log("Vendor Role Assignment Verified")

    return vendor['id']

def test_catalog_flow(session):
    log("--- Testing Catalog Flow ---")
    
    # 1. Create Item
    suffix = int(time.time())
    item_data = {
        "name": f"Integration Test Item {suffix}",
        "description": "Auto-generated test item",
        "type": "product",
        "reference_cost": 500,
        "default_price": 1000,
        "unit": "PC"
    }
    
    resp = session.post(f"{BASE_URL}/catalog-items/", json=item_data)
    if resp.status_code != 201 and resp.status_code != 200:
         log(f"Create Catalog Item Failed: {resp.status_code} {resp.text}", "ERROR")
         return None
         
    item = resp.json()
    log(f"Created Catalog Item: {item['id']}")
    return item['id']

def test_rfq_flow(session, customer_id, vendor_id, item_id):
    log("--- Testing RFQ Flow ---")
    
    # 1. Create RFQ
    suffix = int(time.time())
    rfq_data = {
        "customer_id": customer_id,
        "vendor_id": vendor_id,
        "project_name": f"Integration Test Project {suffix}",
        "due_date": "2026-12-31"
    }
    resp = session.post(f"{BASE_URL}/rfqs/", json=rfq_data)
    if resp.status_code != 201 and resp.status_code != 200:
        log(f"Create RFQ Failed: {resp.text}", "ERROR")
        return None
        
    rfq = resp.json()
    rfq_id = rfq['id']
    log(f"Created RFQ: {rfq_id} ({rfq['rfq_no']})")
    
    # 2. Add Items
    if item_id:
        update_payload = {
            "items": [
                {
                    "catalog_item_id": item_id,
                    "quantity": 5,
                    "unit_price": 900,
                    # When creating item, we need basic fields from RFQItemCreate?
                    # RFQItemCreate inherits RFQItemBase: name, item_type needed if not from catalog?
                    # But RFQItemCreate has catalog_item_id.
                    # Let's hope backend handles copy from catalog.
                    # Per schema RFQItemCreate: name, item_type are required in Base. 
                    # If I pass catalog_item_id, does backend populate them? 
                    # Usually clean implementation does. I will provide name/type just in case.
                    "name": "Integration Test Item",
                    "item_type": "product"
                }
            ]
        }
        
        resp = session.put(f"{BASE_URL}/rfqs/{rfq_id}", json=update_payload)
        
        if resp.status_code != 200:
            log(f"Add Items (Update RFQ) Failed: {resp.text}", "ERROR")
        else:
            updated_rfq = resp.json()
            # Verify items are there
            # RFQDetailResponse -> current_version -> items
            if 'current_version' in updated_rfq and len(updated_rfq['current_version']['items']) > 0:
                log(f"Items Added Successfully: {len(updated_rfq['current_version']['items'])} items")
            else:
                 log("Items Added but not found in response?", "WARNING")

            
    # 3. Change Status
    status_payload = {"status": "vendor_quoting"}
    resp = session.patch(f"{BASE_URL}/rfqs/{rfq_id}/status", json=status_payload)
    if resp.status_code != 200:
        log(f"Status Update Failed: {resp.text}", "ERROR")
    else:
        log("Updated Status to vendor_quoting")

    return rfq_id


def test_promotion_and_quote_flow(session, customer_id, item_id):
    log("--- Testing Promotion + Quote Flow ---")

    promo_payload = {
        "promotion_name": f"Integration Promo {int(time.time())}",
        "description": "Integration test promotion",
        "type": "percentage",
        "discount_value": 10,
        "minimum_order_amount": 100,
        "scope": "all_products",
        "start_at": "2026-01-01T00:00:00+00:00",
        "end_at": "2026-12-31T23:59:59+00:00",
        "is_active": True,
    }
    resp = session.post(f"{BASE_URL}/promotions", json=promo_payload)
    if resp.status_code != 200:
        log(f"Create Promotion Failed: {resp.status_code} {resp.text}", "ERROR")
        return
    promotion = resp.json()
    log(f"Created Promotion: {promotion['promotion_code']}")

    quote_payload = {
        "customer_id": customer_id,
        "title": f"Integration Quote {int(time.time())}",
        "tax_setting": "taxable_5",
        "promotion_id": promotion["id"],
        "subtotal": 1000,
        "tax_total": 45,
        "total": 945,
        "items": [
            {
                "name": "Integration Test Item",
                "quantity": 1,
                "unit": "pcs",
                "unit_price": 1000,
                "tax_category_name": "taxable_5",
                "tax_rate": 0.05,
                "subtotal": 1000,
                "tax_amount": 50,
                "total_amount": 1050,
                "line_total": 1050,
                "catalog_item_id": item_id,
            }
        ],
    }
    resp = session.post(f"{BASE_URL}/quotes", json=quote_payload)
    if resp.status_code != 200:
        log(f"Create Quote Failed: {resp.status_code} {resp.text}", "ERROR")
        return
    quote = resp.json()
    if str(quote.get("promotion_discount_amount")) not in {"100", "100.0", "100.00"}:
        log(f"Quote promotion discount validation failed: {quote.get('promotion_discount_amount')}", "ERROR")
    else:
        log("Quote promotion calculation verified")

    resp = session.patch(f"{BASE_URL}/quotes/{quote['id']}/status", json={"status": "confirmed"})
    if resp.status_code != 200:
        log(f"Confirm Quote Failed: {resp.status_code} {resp.text}", "ERROR")
        return
    confirmed_quote = resp.json()
    if not confirmed_quote.get("promotion_name_snapshot"):
        log("Quote promotion snapshot missing", "ERROR")
    else:
        log("Quote promotion snapshot verified")

    resp = session.post(f"{BASE_URL}/quotes/{quote['id']}/create-invoice")
    if resp.status_code != 200:
        log(f"Create Invoice From Quote Failed: {resp.status_code} {resp.text}", "ERROR")
        return
    invoice = resp.json()
    if str(invoice.get("promotion_discount_amount")) != str(confirmed_quote.get("promotion_discount_amount")):
        log("Invoice promotion snapshot mismatch", "ERROR")
    else:
        log("Invoice promotion snapshot verified")


if __name__ == "__main__":
    try:
        log("Starting System Verification...")
        
        session = requests.Session()
        # Get CSRF
        csrf_resp = session.get(f"{BASE_URL}/auth/csrf")
        if csrf_resp.status_code == 200:
            csrf = csrf_resp.json().get("csrf_token")
            session.headers.update({"x-csrf-token": csrf})
            log(f"Got CSRF Token: {csrf[:10]}...")
        else:
            log("Failed to get CSRF token", "WARNING")
            
        # Try to login
        if not setup_and_login(session):
            log("Aborting verification due to login failure", "CRITICAL")
            exit(1)

        cid = test_customer_flow(session)
        vid = test_vendor_flow(session)
        
        if cid and vid:
            iid = test_catalog_flow(session)
            test_rfq_flow(session, cid, vid, iid)
            if iid:
                test_promotion_and_quote_flow(session, cid, iid)
        
        log("Verification Completed")
    except Exception as e:
        log(f"Script Error: {e}", "CRITICAL")
