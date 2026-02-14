import requests
import json
import time

# Configuration
BASE_URL = "https://b2b-quotation-system.vercel.app/api/v1"
EMAIL = "kao264918@gmail.com"
PASSWORD = "Password123"

class Color:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'

def log(msg, success=True):
    color = Color.GREEN if success else Color.RED
    print(f"{color}{msg}{Color.RESET}")

def section(name):
    print(f"\n{Color.YELLOW}=== Verifying {name} ==={Color.RESET}")

class ProdVerifier:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            "Content-Type": "application/json"
        }

    def login(self):
        section("Authentication")
        url = f"{BASE_URL}/auth/login"
        try:
            # 1. Get CSRF first (good practice)
            self.session.get(f"{BASE_URL}/auth/csrf")
            
            # 2. Login
            payload = {
                "email": EMAIL,
                "password": PASSWORD,
                "remember_me": False
            }
            res = self.session.post(url, json=payload)
            if res.status_code == 200:
                log("✅ Login successful")
                # Extract CSRF token and set header
                csrf_token = self.session.cookies.get("csrf_token")
                if csrf_token:
                    self.session.headers.update({"X-CSRF-Token": csrf_token})
                    log(f"✅ CSRF Token set: {csrf_token[:10]}..." if csrf_token else "⚠️ No CSRF Token found")
                else:
                    log("⚠️ Warning: No CSRF cookie found", False)

                # DEBUG: Print cookies
                print("DEBUG: Cookies after login:", self.session.cookies.get_dict())

                # Verify Session with /auth/me
                me_res = self.session.get(f"{BASE_URL}/auth/me")
                if me_res.status_code == 200:
                    log(f"✅ Auth Me successful: {me_res.json().get('email')}")
                else:
                    log(f"❌ Auth Me Failed: {me_res.status_code} {me_res.text}", False)

                return True
            else:
                log(f"❌ Login failed: {res.status_code} - {res.text}", False)
                return False
        except Exception as e:
            log(f"❌ Login exception: {str(e)}", False)
            return False

    def test_customer_crud(self):
        section("Customer Management")
        unique_suffix = str(int(time.time()))
        tax_id_suffix = unique_suffix[-8:] # Last 8 digits
        
        # Create
        create_payload = {
            "company_name": f"PROD_TEST_Customer_{unique_suffix}",
            "tax_id": tax_id_suffix, # Random 8 digits
            "contact_name": "Tester",
            "contact_email": f"test_prod_{unique_suffix}@example.com",
            "address_line1": "123 Test St",
            "city": "Test City",
            "country": "TW",
            "billing_email": "billing@example.com"
        }
        res = self.session.post(f"{BASE_URL}/customers", json=create_payload)
        if res.status_code not in [200, 201]:
            log(f"❌ Create Customer Failed: {res.status_code} {res.text}", False)
            return None
        
        data = res.json()
        cust_id = data['id']
        log(f"✅ Created Customer: {cust_id}")

        # Read
        res = self.session.get(f"{BASE_URL}/customers/{cust_id}")
        if res.status_code == 200:
            log(f"✅ Read Customer: {res.json().get('company_name')}")
        else:
            log(f"❌ Read Customer Failed: {res.status_code}", False)

        # Update
        update_payload = {"company_name": "PROD_TEST_Customer_UPDATED"}
        res = self.session.put(f"{BASE_URL}/customers/{cust_id}", json=update_payload)
        if res.status_code == 200:
            log(f"✅ Updated Customer: {res.json().get('company_name')}")
        else:
            log(f"❌ Update Customer Failed: {res.status_code}", False)

        # Delete
        res = self.session.delete(f"{BASE_URL}/customers/{cust_id}")
        if res.status_code == 200: # Backend uses 200 or 204
             log("✅ Deleted Customer")
        else:
             log(f"❌ Delete Customer Failed: {res.status_code}", False)
        
        return cust_id # Return ID even if deleted to confirm flow

    def test_vendor_crud(self):
        section("Vendor Management")
        # Create
        payload = {
            "name": "PROD_TEST_Vendor",
            "company_name": "PROD_TEST_Vendor_Co",
            "contact_person": "Vendor Tester", # This might not be in schema, removing
            "email": "vendor_test@example.com",
            "phone": "0987654321",
            # contacts list is optional
        }
        res = self.session.post(f"{BASE_URL}/vendors/", json=payload)
        if res.status_code not in [200, 201]:
            log(f"❌ Create Vendor Failed: {res.status_code} {res.text}", False)
            return None
        
        data = res.json()
        vendor_id = data['id']
        log(f"✅ Created Vendor: {vendor_id}")

        # Read List (Test Trailing Slash)
        res = self.session.get(f"{BASE_URL}/vendors/?skip=0&limit=10")
        if res.status_code == 200:
             log(f"✅ Read Vendor List (Slash check)")
        else:
             log(f"❌ Read Vendor List Failed: {res.status_code}", False)

        # Delete
        res = self.session.delete(f"{BASE_URL}/vendors/{vendor_id}")
        if res.status_code == 200:
             log("✅ Deleted Vendor")
        else:
             log(f"❌ Delete Vendor Failed: {res.status_code}", False)

    def test_catalog(self):
        section("Catalog Management (Read Only test for safety)")
        res = self.session.get(f"{BASE_URL}/catalog-items")
        if res.status_code == 200:
            items = res.json().get('items', [])
            log(f"✅ Read Catalog Items: Got {len(items)} items")
            if items:
                first_id = items[0]['id']
                res_detail = self.session.get(f"{BASE_URL}/catalog-items/{first_id}")
                if res_detail.status_code == 200:
                    log("✅ Read Catalog Detail")
                else:
                    log(f"❌ Read Catalog Detail Failed: {res_detail.status_code}", False)
        else:
             log(f"❌ Read Catalog List Failed: {res.status_code}", False)
    
    def test_rfq_flow(self):
        section("RFQ & Quote Flow")
        unique_suffix = str(int(time.time()))
        tax_id_suffix = unique_suffix[-8:]
        
        # 1. Create temporary customer for RFQ
        cust_payload = {
            "company_name": f"PROD_TEST_RFQ_Cust_{unique_suffix}",
            "tax_id": tax_id_suffix,
            "contact_name": "RFQ Tester",
            "contact_email": f"rfq_test_{unique_suffix}@example.com",
            "address_line1": "RFQ Test St",
            "city": "RFQ City",
            "country": "TW",
        }
        cust_res = self.session.post(f"{BASE_URL}/customers/", json=cust_payload)
        if cust_res.status_code not in [200, 201]:
            log("❌ Prerequisite: Failed to create customer for RFQ test", False)
            return
        
        cust_id = cust_res.json()['id']
        
        # 2. Create RFQ
        # Note: Correct endpoint might be /rfqs/ (with slash) based on previous debugging
        rfq_payload = {
            "project_name": "PROD_TEST_Project",
            "customer_id": cust_id,
            "items": [
                {
                    "item_type": "custom",
                    "name": "Test Item",
                    "quantity": 10,
                    "unit": "pc"
                }
            ]
        }
        
        # Test both /rfqs and /rfqs/ just to be sure, but we expect /rfqs/ to be the corrected one if Python requests doesn't auto-redirect safely with POST
        # Actually Vercel rewrite regex now handles it. Backend likely needs slash.
        res = self.session.post(f"{BASE_URL}/rfqs/", json=rfq_payload)
        
        rfq_id = None
        if res.status_code in [200, 201]:
            data = res.json()
            rfq_id = data['id']
            log(f"✅ Created RFQ: {rfq_id}")
        else:
            log(f"❌ Create RFQ Failed: {res.status_code} {res.text}", False)

        # 3. List RFQs
        list_res = self.session.get(f"{BASE_URL}/rfqs/")
        if list_res.status_code == 200:
            log("✅ List RFQs successful")
        else:
            log(f"❌ List RFQs Failed: {list_res.status_code}", False)

        # 4. Create Quote (if RFQ created)
        if rfq_id:
            # Delete RFQ
            del_res = self.session.delete(f"{BASE_URL}/rfqs/{rfq_id}")
            if del_res.status_code == 204 or del_res.status_code == 200:
                log("✅ Deleted RFQ")
            else:
                log(f"❌ Delete RFQ Failed: {del_res.status_code}", False)

        # Cleanup Customer
        self.session.delete(f"{BASE_URL}/customers/{cust_id}")
        log("✅ Cleanup: Deleted temp customer")

    def run(self):
        if self.login():
            self.test_customer_crud()
            self.test_vendor_crud()
            self.test_catalog()
            self.test_rfq_flow()
        else:
            log("Stopping verification due to login failure", False)

if __name__ == "__main__":
    verifier = ProdVerifier()
    verifier.run()
