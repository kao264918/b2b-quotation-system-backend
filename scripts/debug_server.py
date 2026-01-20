import requests
import json

BASE_URL = "http://localhost:8001/api/v1"

def debug_create_customer():
    print("--- Debugging Create Customer ---")
    data = {
        "company_name": "Debug Corp",
        "tax_id": "88888888",
        "contact_name": "Debug User",
        "contact_email": "debug@example.com",
        "address_line1": "123 Debug St",
        "city": "Debug City",
        "country": "TW",
        "roles": ["customer"]
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/customers/", json=data)
        print(f"Status: {resp.status_code}")
        print("Headers:", resp.headers)
        print("Body:", resp.text)
    except Exception as e:
        print(f"Request Exception: {e}")

def debug_get_customers():
    print("--- Debugging Get Customers ---")
    try:
        resp = requests.get(f"{BASE_URL}/customers/")
        print(f"Status: {resp.status_code}")
        print("Body sample:", resp.text[:200])
    except Exception as e:
        print(f"Request Exception: {e}")

def debug_get_rfqs():
    print("--- Debugging Get RFQs ---")
    try:
        resp = requests.get(f"{BASE_URL}/rfqs/")
        print(f"Status: {resp.status_code}")
        print("Body sample:", resp.text[:200])
    except Exception as e:
        print(f"Request Exception: {e}")

if __name__ == "__main__":
    debug_get_rfqs()
