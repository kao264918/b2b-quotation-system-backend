import requests
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000/api/v1/auth"

def verify_auth_flow():
    session = requests.Session()
    
    # 1. Login
    login_payload = {
        "email": "admin@example.com",
        "password": "password123",
        "remember_me": True
    }
    
    logger.info("Attempting login...")
    try:
        response = session.post(f"{BASE_URL}/login", json=login_payload)
    except requests.exceptions.ConnectionError:
        logger.error("Could not connect to backend at http://localhost:8000. Is it running?")
        sys.exit(1)

    if response.status_code != 200:
        logger.error(f"Login failed: {response.status_code} - {response.text}")
        sys.exit(1)
        
    logger.info(f"Login successful. Cookies: {session.cookies.get_dict()}")
    
    if "session_id" not in session.cookies:
        logger.error("Session cookie 'session_id' not found!")
        sys.exit(1)

    # 2. Get Me
    logger.info("Fetching /me...")
    response = session.get(f"{BASE_URL}/me")
    if response.status_code != 200:
        logger.error(f"Get Me failed: {response.status_code} - {response.text}")
        sys.exit(1)
        
    user_data = response.json()
    logger.info(f"User retrieved: {user_data.get('email')}")
    
    if user_data.get("email") != "admin@example.com":
        logger.error("User email mismatch!")
        sys.exit(1)

    # 3. Logout
    logger.info("Logging out...")
    response = session.post(f"{BASE_URL}/logout")
    if response.status_code != 200:
        logger.error(f"Logout failed: {response.status_code} - {response.text}")
        sys.exit(1)

    # 4. Verify Logout
    logger.info("Verifying logout...")
    response = session.get(f"{BASE_URL}/me")
    if response.status_code != 401:
        logger.error(f"Logout verification failed. Expected 401, got {response.status_code}")
        sys.exit(1)
        
    logger.info("Verification Complete: SUCCESS")

if __name__ == "__main__":
    verify_auth_flow()
