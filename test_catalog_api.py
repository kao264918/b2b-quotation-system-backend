#!/usr/bin/env python3
"""
Catalog API Test Suite
Tests all endpoints and validates MVP requirements
"""
import requests
import json
from datetime import datetime
from typing import Dict, Any

BASE_URL = "http://localhost:8000/api/v1/catalog/items"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def log_test(name: str):
    print(f"\n{Colors.BLUE}▶ Testing: {name}{Colors.END}")

def log_pass(message: str):
    print(f"{Colors.GREEN}✓ {message}{Colors.END}")

def log_fail(message: str):
    print(f"{Colors.RED}✗ {message}{Colors.END}")

def log_info(message: str):
    print(f"{Colors.YELLOW}ℹ {message}{Colors.END}")

# Track created items for cleanup
created_items = []

def cleanup_items():
    """Delete all created test items"""
    log_info(f"Cleaning up {len(created_items)} test items...")
    for item_id in created_items:
        try:
            requests.delete(f"{BASE_URL}/{item_id}")
        except:
            pass

def test_create_product():
    """Test 1: Create product with auto-generated item_no"""
    log_test("Create Product (auto item_no, default unit)")
    
    payload = {
        "name": "Test Laptop Stand",
        "type": "product",
        "reference_cost": 150.00,
        "default_price": 300.00,
        "description": "Test product item"
    }
    
    response = requests.post(BASE_URL, json=payload)
    
    if response.status_code == 201:
        data = response.json()
        created_items.append(data['id'])
        
        assert 'item_no' in data, "Missing item_no"
        assert data['item_no'].startswith('P-'), f"Expected P- prefix, got {data['item_no']}"
        assert data['unit'] == 'pcs', f"Expected default unit 'pcs', got {data['unit']}"
        assert data['type'] == 'product'
        
        log_pass(f"Created: {data['name']} (item_no: {data['item_no']}, unit: {data['unit']})")
        return data
    else:
        log_fail(f"Status {response.status_code}: {response.text}")
        return None

def test_create_service():
    """Test 2: Create service"""
    log_test("Create Service (S- prefix)")
    
    payload = {
        "name": "Test Installation Service",
        "type": "service",
        "reference_cost": 500.00,
        "default_price": 1000.00
    }
    
    response = requests.post(BASE_URL, json=payload)
    
    if response.status_code == 201:
        data = response.json()
        created_items.append(data['id'])
        
        assert data['item_no'].startswith('S-'), f"Expected S- prefix, got {data['item_no']}"
        assert data['unit'] == 'pcs'
        
        log_pass(f"Created: {data['name']} (item_no: {data['item_no']})")
        return data
    else:
        log_fail(f"Status {response.status_code}: {response.text}")
        return None

def test_create_output():
    """Test 3: Create output"""
    log_test("Create Output (O- prefix, unit=材)")
    
    payload = {
        "name": "Test Steel Sheet",
        "type": "output",
        "reference_cost": 200.00,
        "default_price": 400.00
    }
    
    response = requests.post(BASE_URL, json=payload)
    
    if response.status_code == 201:
        data = response.json()
        created_items.append(data['id'])
        
        assert data['item_no'].startswith('O-'), f"Expected O- prefix, got {data['item_no']}"
        assert data['unit'] == '材', f"Expected unit '材', got {data['unit']}"
        
        log_pass(f"Created: {data['name']} (item_no: {data['item_no']}, unit: {data['unit']})")
        return data
    else:
        log_fail(f"Status {response.status_code}: {response.text}")
        return None

def test_duplicate_name():
    """Test 4: Duplicate name should return 409"""
    log_test("Duplicate Name Validation (409)")
    
    # Create first item
    payload1 = {
        "name": "Test Duplicate Item",
        "type": "product",
        "reference_cost": 100.00,
        "default_price": 200.00
    }
    resp1 = requests.post(BASE_URL, json=payload1)
    if resp1.status_code == 201:
        created_items.append(resp1.json()['id'])
    
    # Try to create duplicate
    payload2 = {
        "name": "Test Duplicate Item",  # Same name
        "type": "service",  # Different type
        "reference_cost": 150.00,
        "default_price": 300.00
    }
    resp2 = requests.post(BASE_URL, json=payload2)
    
    if resp2.status_code == 409:
        log_pass("409 Conflict returned for duplicate name")
    else:
        log_fail(f"Expected 409, got {resp2.status_code}")

def test_pagination():
    """Test 5: Pagination with filters"""
    log_test("Pagination & Filters")
    
    # Create multiple items
    for i in range(3):
        payload = {
            "name": f"Test Pagination Item {i+1}",
            "type": "product",
            "reference_cost": 100.00,
            "default_price": 200.00
        }
        resp = requests.post(BASE_URL, json=payload)
        if resp.status_code == 201:
            created_items.append(resp.json()['id'])
    
    # Test pagination
    response = requests.get(f"{BASE_URL}?page=1&pageSize=50&status=active")
    
    if response.status_code == 200:
        data = response.json()
        
        assert 'items' in data, "Missing items"
        assert 'meta' in data, "Missing meta"
        assert 'totalCount' in data['meta']
        assert 'page' in data['meta']
        assert 'pageSize' in data['meta']
        assert 'totalPages' in data['meta']
        
        log_pass(f"Pagination OK: {data['meta']['totalCount']} items, page {data['meta']['page']}/{data['meta']['totalPages']}")
    else:
        log_fail(f"Status {response.status_code}")

def test_filter_by_type():
    """Test 6: Filter by type"""
    log_test("Filter by Type")
    
    response = requests.get(f"{BASE_URL}?type=product")
    
    if response.status_code == 200:
        data = response.json()
        items = data['items']
        
        all_products = all(item['type'] == 'product' for item in items)
        
        if all_products:
            log_pass(f"Type filter OK: {len(items)} products")
        else:
            log_fail("Found non-product items in result")
    else:
        log_fail(f"Status {response.status_code}")

def test_search():
    """Test 7: Search functionality"""
    log_test("Search by Name")
    
    # Create item with specific name
    payload = {
        "name": "SEARCHABLE_UNIQUE_ITEM",
        "type": "product",
        "reference_cost": 100.00,
        "default_price": 200.00
    }
    resp = requests.post(BASE_URL, json=payload)
    if resp.status_code == 201:
        created_items.append(resp.json()['id'])
    
    # Search
    response = requests.get(f"{BASE_URL}?search=SEARCHABLE")
    
    if response.status_code == 200:
        data = response.json()
        found = any('SEARCHABLE' in item['name'] for item in data['items'])
        
        if found:
            log_pass("Search OK: Found item")
        else:
            log_fail("Search failed: Item not found")
    else:
        log_fail(f"Status {response.status_code}")

def test_get_by_id(item_id: str):
    """Test 8: Get item by ID"""
    log_test("Get Item by ID")
    
    response = requests.get(f"{BASE_URL}/{item_id}")
    
    if response.status_code == 200:
        data = response.json()
        log_pass(f"Retrieved: {data['name']} ({data['item_no']})")
        return data
    else:
        log_fail(f"Status {response.status_code}")
        return None

def test_update(item_id: str):
    """Test 9: Update item"""
    log_test("Update Item")
    
    payload = {
        "description": "Updated description",
        "default_price": 350.00
    }
    
    response = requests.put(f"{BASE_URL}/{item_id}", json=payload)
    
    if response.status_code == 200:
        data = response.json()
        assert data['description'] == "Updated description"
        assert float(data['default_price']) == 350.00
        
        log_pass("Updated successfully")
    else:
        log_fail(f"Status {response.status_code}")

def test_inactivate(item_id: str):
    """Test 10: Inactivate item"""
    log_test("Inactivate Item")
    
    response = requests.post(f"{BASE_URL}/{item_id}/inactivate")
    
    if response.status_code == 200:
        data = response.json()
        
        if data['status'] == 'inactive':
            log_pass("Inactivated successfully")
            
            # Verify not in active list
            list_resp = requests.get(f"{BASE_URL}?status=active")
            if list_resp.status_code == 200:
                active_items = list_resp.json()['items']
                if not any(item['id'] == item_id for item in active_items):
                    log_pass("Confirmed: Not in active list")
                else:
                    log_fail("Item still in active list")
        else:
            log_fail(f"Status is {data['status']}, expected 'inactive'")
    else:
        log_fail(f"Status {response.status_code}")

def test_soft_delete(item_id: str):
    """Test 11: Soft delete"""
    log_test("Soft Delete")
    
    response = requests.delete(f"{BASE_URL}/{item_id}")
    
    if response.status_code == 200:
        log_pass("Deleted successfully")
        
        # Verify not in list
        list_resp = requests.get(f"{BASE_URL}")
        if list_resp.status_code == 200:
            items = list_resp.json()['items']
            if not any(item['id'] == item_id for item in items):
                log_pass("Confirmed: Not in list")
            else:
                log_fail("Item still in list")
        
        # Verify 404 on get
        get_resp = requests.get(f"{BASE_URL}/{item_id}")
        if get_resp.status_code == 404:
            log_pass("Confirmed: Returns 404")
        else:
            log_fail(f"Expected 404, got {get_resp.status_code}")
    else:
        log_fail(f"Status {response.status_code}")

def test_audit_log():
    """Test 12: Check audit log exists (via database)"""
    log_test("Audit Log Check")
    log_info("Audit log validation requires database access - skipping automated test")
    log_info("Manual verification: SELECT * FROM audit_logs WHERE entity_type='catalog_item'")

def main():
    print(f"{Colors.BLUE}{'='*60}")
    print("Catalog API Test Suite")
    print(f"{'='*60}{Colors.END}\n")
    print(f"Base URL: {BASE_URL}")
    print(f"Time: {datetime.now().isoformat()}\n")
    
    try:
        # Basic CRUD tests
        product = test_create_product()
        service = test_create_service()
        output = test_create_output()
        
        # Validation tests
        test_duplicate_name()
        
        # Query tests
        test_pagination()
        test_filter_by_type()
        test_search()
        
        # Operations on first product
        if product:
            test_get_by_id(product['id'])
            test_update(product['id'])
            test_inactivate(product['id'])
        
        # Soft delete test (use service)
        if service:
            test_soft_delete(service['id'])
        
        # Audit log
        test_audit_log()
        
        print(f"\n{Colors.GREEN}{'='*60}")
        print("All tests completed!")
        print(f"{'='*60}{Colors.END}\n")
        
    except Exception as e:
        print(f"\n{Colors.RED}Test suite error: {e}{Colors.END}")
    finally:
        cleanup_items()

if __name__ == "__main__":
    main()
