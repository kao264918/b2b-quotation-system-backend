import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.models.user import User, UserStatus, UserRole
from app.models.token import VerificationToken
from app.deps.auth import get_session_token_hash
from app.database import SessionLocal
from app.crud import user as crud_user
import uuid

@pytest.fixture(scope="module")
def db():
    yield SessionLocal()

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient, db: Session):
    email = f"admin_strict_{uuid.uuid4().hex[:8]}@example.com"
    password = "AdminPassword123!"
    
    # create(db, email, password, full_name, is_superuser, is_active)
    user = crud_user.user.create(
        db,
        email=email,
        password=password,
        full_name="Admin User",
        is_superuser=True,
        is_active=True
    )
    # Manually set other fields not in create()
    user.role = UserRole.ADMIN
    user.status = UserStatus.ACTIVE
    user.is_verified = True
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Verify creation
    assert user.is_superuser is True
    assert user.role == UserRole.ADMIN
    
    login_data = {
        "email": email,
        "password": password,
        "remember_me": False
    }
    r = client.post("/api/v1/auth/login", json=login_data)
    assert r.status_code == 200, f"Login failed: {r.text}"
    tokens = r.json()
    
    # Get CSRF token
    r = client.get("/api/v1/auth/csrf")
    assert r.status_code == 200
    csrf_token = r.json()["csrf_token"]
    
    return {
        "Authorization": f"Bearer {tokens['access_token']}",
        "X-CSRF-Token": csrf_token
    }

def test_invite_flow_strict_alignment(client, db: Session, superuser_token_headers):
    # 1. Admin Invite User (No Name)
    email = f"strict_test_{uuid.uuid4().hex[:8]}@example.com"
    invite_payload = {
        "email": email,
        "full_name": None, 
        "company_name": "Strict Co"
    }
    r = client.post("/api/v1/auth/invite", json=invite_payload, headers=superuser_token_headers)
    assert r.status_code == 200, f"Invite failed: {r.text}"
    user_data = r.json()
    
    # 2. Get Token from DB
    user = db.query(User).filter(User.id == user_data["id"]).first()
    assert user is not None
    assert user.status == UserStatus.PENDING_PASSWORD
    assert user.full_name is None
    
    token_obj = db.query(VerificationToken).filter(VerificationToken.user_id == user.id).first()
    assert token_obj is not None
    
    # Token manipulation for testing
    token_str = f"test_token_strict_{uuid.uuid4().hex}"
    token_hash = get_session_token_hash(token_str)
    
    token_obj.token_hash = token_hash
    db.commit()
    
    # 3. Verify Token Info
    r = client.get(f"/api/v1/auth/verify-token-info?token={token_str}")
    assert r.status_code == 200
    data = r.json()
    assert data["valid"] is True
    assert data["email"] == email
    assert data["full_name"] is None 
    
    # 4. Reset Password (with Name)
    reset_payload = {
        "token": token_str,
        "password": "NewStrongPassword1!",
        "confirmPassword": "NewStrongPassword1!",
        "full_name": "Strict User Completed"
    }
    
    r = client.post("/api/v1/auth/reset-password", json=reset_payload)
    assert r.status_code == 200, f"Reset failed: {r.text} | Token: {token_str}"
    
    # 5. Verify User Status
    db.refresh(user)
    assert user.status == UserStatus.ACTIVE
    assert user.is_verified is True
    assert user.full_name == "Strict User Completed"
    
    # 6. Verify Token Deleted
    token_obj = db.query(VerificationToken).filter(VerificationToken.user_id == user.id).first()
    assert token_obj is None

def test_invite_flow_with_name_provided(client, db: Session, superuser_token_headers):
    # 1. Admin Invite User (With Name)
    email = f"strict_test_named_{uuid.uuid4().hex[:8]}@example.com"
    invite_payload = {
        "email": email,
        "full_name": "Predefined Name",
        "company_name": "Strict Co"
    }
    r = client.post("/api/v1/auth/invite", json=invite_payload, headers=superuser_token_headers)
    assert r.status_code == 200
    user_data = r.json()
    
    user = db.query(User).filter(User.id == user_data["id"]).first()
    token_obj = db.query(VerificationToken).filter(VerificationToken.user_id == user.id).first()
    
    # Hack token
    token_str = f"test_token_strict_{uuid.uuid4().hex}"
    token_hash = get_session_token_hash(token_str)
    token_obj.token_hash = token_hash
    db.commit()
    
    # Verify Info
    r = client.get(f"/api/v1/auth/verify-token-info?token={token_str}")
    assert r.status_code == 200
    data = r.json()
    assert data["full_name"] == "Predefined Name"
    
    # Reset Password (No Name sent)
    reset_payload = {
        "token": token_str,
        "password": "NewStrongPassword1!"
    }
    r = client.post("/api/v1/auth/reset-password", json=reset_payload)
    assert r.status_code == 200
    
    db.refresh(user)
    assert user.full_name == "Predefined Name" 
    assert user.status == UserStatus.ACTIVE
