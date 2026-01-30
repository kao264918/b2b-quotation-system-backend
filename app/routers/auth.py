from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.auth import LoginRequest, UserResponse
from app.crud import user as crud_user
from app.models.session import RefreshSession
from app.models.user import User
from app.config import settings
from datetime import datetime, timedelta, timezone
import secrets
import hashlib

router = APIRouter()

def get_session_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    session_token = request.cookies.get("session_id")
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    token_hash = get_session_token_hash(session_token)
    
    # Clean up expired sessions occasionally? Or just check expiry here.
    session = db.query(RefreshSession).filter(RefreshSession.token_hash == token_hash).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session"
        )
        
    if session.expires_at < datetime.now(timezone.utc):
        db.delete(session)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired"
        )
        
    return session.user

@router.post("/login", response_model=UserResponse)
def login(login_data: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = crud_user.user.authenticate(db, email=login_data.email, password=login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )

    # Create session
    session_token = secrets.token_urlsafe(32)
    token_hash = get_session_token_hash(session_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.SESSION_EXPIRE_DAYS)
    
    db_session = RefreshSession(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at
    )
    db.add(db_session)
    db.commit()
    
    # Set Cookie
    # Production Safety:
    # - Secure: True in production (HTTPS required)
    # - HttpOnly: True (No JS access)
    # - SameSite: Lax (Allows top-level navigation, blocks CSRF)
    
    is_production = settings.ENVIRONMENT == "production"
    
    response.set_cookie(
        key="session_id",
        value=session_token,
        httponly=True,
        max_age=settings.SESSION_EXPIRE_DAYS * 24 * 60 * 60,
        expires=expires_at,
        samesite="lax",
        secure=is_production, 
        path="/"
    )
    
    return user

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/logout")
def logout(response: Response, request: Request, db: Session = Depends(get_db)):
    session_token = request.cookies.get("session_id")
    if session_token:
        token_hash = get_session_token_hash(session_token)
        db.query(RefreshSession).filter(RefreshSession.token_hash == token_hash).delete()
        db.commit()
    
    response.delete_cookie("session_id")
    return {"message": "Logged out successfully"}
