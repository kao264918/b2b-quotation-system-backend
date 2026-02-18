from fastapi.testclient import TestClient
from app.main import app
from app.schemas.auth import InviteRequest

import uuid

client = TestClient(app)

def test_request_access_endpoint():
    email = f"test_e2e_{uuid.uuid4()}@example.com"
    payload = {
        "email": email,
        "full_name": "E2E Test User",
        "company_name": "E2E Corp",
        "note": "Testing 500"
    }
    
    print(f"Sending request to /api/v1/auth/request-access with email: {email}")
    
    response = client.post("/api/v1/auth/request-access", json=payload)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code != 200:
        print("Test FAILED")
    else:
        print("Test PASSED")

if __name__ == "__main__":
    test_request_access_endpoint()
