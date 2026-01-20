import requests
import json
import time

BASE_URL = "http://localhost:8000/api/v1"

def log(msg, status="INFO"):
    print(f"[{status}] {msg}")

def test_customer_flow():
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
    
    resp = requests.post(f"{BASE_URL}/customers/", json=customer_data)
    if resp.status_code != 200:
        log(f"Create Customer Failed: {resp.text}", "ERROR")
        return None
    
    customer = resp.json()
    log(f"Created Customer: {customer['id']}")
    
    # 2. Get Customer List
    resp = requests.get(f"{BASE_URL}/customers/?page=1&page_size=10")
    if resp.status_code != 200:
        log("Get Customers Failed", "ERROR")
    else:
        log(f"Fetched Customer List: Found {len(resp.json()['items'])} items")

    return customer['id']

def test_vendor_flow():
    log("--- Testing Vendor Flow ---")
    suffix = int(time.time())
    vendor_data = {
        "name": f"Test Vendor {suffix}",
        "company_name": f"Test Vendor Corp {suffix}",
        "tax_id": f"123{suffix % 100000:05d}",
        "email": f"vendor_{suffix}@test.com",
        "status": "active"
    }
    
    resp = requests.post(f"{BASE_URL}/vendors/", json=vendor_data)
    if resp.status_code != 200:
        # Check if 200 or 201
        log(f"Create Vendor Failed: {resp.status_code} {resp.text}", "ERROR")
        return None
        
    vendor = resp.json()
    log(f"Created Vendor: {vendor['id']}")
    return vendor['id']

def test_catalog_flow():
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
    
    resp = requests.post(f"{BASE_URL}/catalog-items/", json=item_data)
    if resp.status_code != 201 and resp.status_code != 200:
         log(f"Create Catalog Item Failed: {resp.status_code} {resp.text}", "ERROR")
         return None
         
    item = resp.json()
    log(f"Created Catalog Item: {item['id']}")
    return item['id']

def test_rfq_flow(customer_id, vendor_id, item_id):
    log("--- Testing RFQ Flow ---")
    
    # 1. Create RFQ
    suffix = int(time.time())
    rfq_data = {
        "customer_id": customer_id,
        "vendor_id": vendor_id,
        "project_name": f"Integration Test Project {suffix}",
        "due_date": "2026-12-31"
    }
    resp = requests.post(f"{BASE_URL}/rfqs/", json=rfq_data)
    if resp.status_code != 201 and resp.status_code != 200:
        log(f"Create RFQ Failed: {resp.text}", "ERROR")
        return None
        
    rfq = resp.json()
    rfq_id = rfq['id']
    log(f"Created RFQ: {rfq_id} ({rfq['rfq_no']})")
    
    # 2. Add Items
    if item_id:
        items_payload = [
            {
                "catalog_item_id": item_id,
                "quantity": 5,
                "unit_price": 900,
                "description": "Test item in RFQ",
                "name": "Integration Test Item (In RFQ)", # RFQ item needs name 
                "item_type": "product"
            }
        ]
        # RFQ update usually uses a PUT to /rfqs/{id}/items or similar. 
        # Checking schema RFQUpdate has `items`.
        # Assuming PUT /rfqs/{id} updates the whole RFQ or just parts. 
        # But wait, looking at router usually:
        # app.include_router(rfqs.router...)
        # Let's try PUT to /rfqs/{id} with items in body first as consistent with schema RFQUpdate
        
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
        
        resp = requests.put(f"{BASE_URL}/rfqs/{rfq_id}", json=update_payload)
        
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
    resp = requests.patch(f"{BASE_URL}/rfqs/{rfq_id}/status", json=status_payload)
    if resp.status_code != 200:
        log(f"Status Update Failed: {resp.text}", "ERROR")
    else:
        log("Updated Status to vendor_quoting")

    return rfq_id


if __name__ == "__main__":
    try:
        log("Starting System Verification...")
        
        cid = test_customer_flow()
        vid = test_vendor_flow()
        
        if cid and vid:
            iid = test_catalog_flow()
            test_rfq_flow(cid, vid, iid)
        
        log("Verification Completed")
    except Exception as e:
        log(f"Script Error: {e}", "CRITICAL")

