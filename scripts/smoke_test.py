import argparse
import requests
import json
import sys

# Default Credentials (from verify_prod_api.py)
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
    print(f"\n{Color.YELLOW}=== {name} ==={Color.RESET}")

class SmokeTester:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "SmokeTester/1.0"
        })

    def fail(self, msg):
        log(f"FAILED: {msg}", False)
        sys.exit(1)

    def check_json_response(self, response, context=""):
        """Verifies response is strictly JSON and not HTML."""
        content_type = response.headers.get("Content-Type", "")
        
        # 1. Check Content-Type header
        if "application/json" not in content_type:
            log(f"⚠️ [Warning] {context}: Content-Type is '{content_type}', expected 'application/json'. Proceeding to check body...", False)

        # 2. Check Body Text for HTML signatures
        text = response.text.strip()
        if text.lower().startswith("<!doctype") or text.lower().startswith("<html"):
            self.fail(f"{context}: Received HTML content! This usually means 404/500 from Vercel/Next.js/Nginx instead of Backend API JSON.")
        
        # 3. Try parsing JSON
        try:
            return response.json()
        except json.JSONDecodeError:
            self.fail(f"{context}: Invalid JSON body. Content preview: {text[:200]}")

    def login(self):
        section("1. Login")
        # 1. CSRF (Best effort)
        try:
            csrf_res = self.session.get(f"{self.base_url}/auth/csrf")
            if csrf_res.status_code == 200:
                csrf_token = csrf_res.json().get("csrf_token")
                if csrf_token:
                    self.session.headers.update({"X-CSRF-Token": csrf_token})
                    log("CSRF Token obtained.")
        except Exception as e:
            log(f"CSRF fetch failed (non-fatal): {e}", False)

        # 2. Login
        url = f"{self.base_url}/auth/login"
        payload = {"email": EMAIL, "password": PASSWORD, "remember_me": False}
        
        res = self.session.post(url, json=payload)
        
        if res.status_code != 200:
            self.fail(f"Login failed: {res.status_code} {res.text}")
            
        data = self.check_json_response(res, "Login")
        log("✅ Login successful")
        
        # Extract Cookie CSRF if available (Django/FastAPI style often sets check cookie)
        csrf_cookie = self.session.cookies.get("csrf_token")
        if csrf_cookie:
             self.session.headers.update({"X-CSRF-Token": csrf_cookie})

    def check_auth_me(self):
        section("2. Auth Me (Session Check)")
        url = f"{self.base_url}/auth/me"
        res = self.session.get(url)
        
        if res.status_code != 200:
            self.fail(f"Auth Me failed: {res.status_code}")
            
        data = self.check_json_response(res, "Auth Me")
        log(f"✅ Auth Me successful. User: {data.get('email')}")

    def check_customers(self):
        section("3. Customers Endpoint")
        # Ensure no accidental HTML response for query params
        url = f"{self.base_url}/customers?skip=0&limit=5"
        res = self.session.get(url)
        
        if res.status_code != 200:
             self.fail(f"Customers list failed: {res.status_code}")
             
        data = self.check_json_response(res, "Customers List")
        
        if isinstance(data, list):
             count = len(data)
             log(f"✅ Customers Endpoint returned list of {count} items.")
        elif isinstance(data, dict) and 'items' in data:
             count = len(data['items'])
             log(f"✅ Customers Endpoint returned paginated object with {count} items.")
        else:
             log(f"⚠️ Customers response structure unexpected: {type(data)}", False)

    def check_rfqs(self):
        section("4. RFQs Endpoint")
        # Test specific regression: "rfqs//?" double slash issue check
        # We will test normal first, then potentially problematic ones if needed, but clean fetch is goal.
        
        url = f"{self.base_url}/rfqs/?skip=0&limit=5" 
        # Note: Backend often requires trailing slash or strict strictness.
        
        res = self.session.get(url)
        
        # If 307 Redirect, requests follows by default, but verify we don't end up at an HTML page
        if res.history:
            log(f"ℹ️ Request was redirected (usually slash related): {[r.status_code for r in res.history]}")

        if res.status_code != 200:
             self.fail(f"RFQs list failed: {res.status_code}")

        data = self.check_json_response(res, "RFQs List")
        
        # Verify structure
        if 'items' in data: # Pagination
             log(f"✅ RFQs Endpoint returned {len(data['items'])} items.")
        elif isinstance(data, list):
             log(f"✅ RFQs Endpoint returned list of {len(data)} items.")
        else:
             log(f"⚠️ RFQs structure unexpected: {type(data)}", False)

    def run(self):
        log(f"🚀 Starting Smoke Test on {self.base_url}...")
        try:
            self.login()
            self.check_auth_me()
            self.check_customers()
            self.check_rfqs()
            section("SUMMARY")
            log("🎉 All Smoke Tests Passed!")
        except Exception as e:
            self.fail(f"Unexpected Exception: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="API Smoke Tester")
    parser.add_argument("--env", type=str, required=True, choices=["dev", "prod"], help="Environment to test")
    args = parser.parse_args()

    if args.env == "dev":
        BASE_URL = "http://localhost:8000/api/v1"
    else:
        # Use direct backend to avoid Vercel redirect issues during smoke test
        BASE_URL = "https://b2b-quotation-system-backend-production.up.railway.app/api/v1"

    tester = SmokeTester(BASE_URL)
    tester.run()
