import sys
import os
import uuid

# Add backend directory to sys.path
sys.path.append(os.path.abspath("/Users/kevinkao/Documents/software building/b2b-quotation-project/b2b-quotation-system-backend"))

from app.database import SessionLocal
from app.models.registration_request import RegistrationRequest, RegistrationStatus
from app.schemas.auth import InviteRequest

def test_request_access_logic():
    db = SessionLocal()
    email = f"test_debug_{uuid.uuid4()}@example.com"
    payload = InviteRequest(
        email=email,
        full_name="Debug User",
        company_name="Debug Corp",
        note="Debugging 500 error"
    )
    
    print(f"Testing with email: {email}")
    
    try:
        # Simulate logic in auth.py
        existing_request = db.query(RegistrationRequest).filter(
            RegistrationRequest.email == payload.email,
            RegistrationRequest.status == RegistrationStatus.PENDING
        ).first()

        if existing_request:
            print("Found existing request (unexpected for new email)")
            existing_request.full_name = payload.full_name or ""
            existing_request.company_name = payload.company_name or ""
            existing_request.note = payload.note
            # existing_request.updated_at = datetime.now(...) 
            db.commit()
        else:
            print("Creating new request...")
            new_request = RegistrationRequest(
                email=payload.email,
                full_name=payload.full_name or "",
                company_name=payload.company_name or "",
                note=payload.note,
                status=RegistrationStatus.PENDING
            )
            db.add(new_request)
            db.commit()
            db.refresh(new_request)
            print(f"Successfully created request with ID: {new_request.id}")
            
    except Exception as e:
        print(f"Caught exception: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    test_request_access_logic()
