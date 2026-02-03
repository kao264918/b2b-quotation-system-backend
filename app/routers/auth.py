from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.auth import LoginRequest, UserResponse, InviteRequest, SetPasswordRequest, ForgotPasswordRequest, ResetPasswordRequest
from app.crud import user as crud_user
from app.models.session import RefreshSession
from app.models.user import User
from app.models.token import VerificationToken, PasswordResetToken
from app.config import settings
from app.services.email import email_service
from datetime import datetime, timedelta, timezone
from fastapi.responses import RedirectResponse
import secrets
import hashlib

router = APIRouter()

def get_session_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    session_token = request.cookies.get("session_id")
    
    # Fallback to Bearer token if cookie is missing (Safari ITP fix)
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header.split(" ")[1]

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
    # Determine session duration based on remember_me
    # Checked: 7 days (settings.SESSION_EXPIRE_DAYS)
    # Unchecked: 1 day
    session_duration_days = settings.SESSION_EXPIRE_DAYS if login_data.remember_me else 1
    expires_at = datetime.now(timezone.utc) + timedelta(days=session_duration_days)
    
    db_session = RefreshSession(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at
    )
    db.add(db_session)
    db.commit()
    
    # Set Cookie
    # Production/Staging Safety for cross-origin:
    # - Secure: True (HTTPS required for cross-origin cookies)
    # - HttpOnly: True (No JS access)
    # - SameSite: None (Required for cross-origin requests)
    
    # For cross-origin (Vercel frontend + Railway backend), we need:
    # - SameSite=None + Secure=True
    is_production = settings.ENVIRONMENT == "production"
    
    response.set_cookie(
        key="session_id",
        value=session_token,
        httponly=True,
        max_age=session_duration_days * 24 * 60 * 60,
        expires=expires_at,
        samesite="none",  # Required for cross-origin
        secure=True,  # Required when samesite=none
        path="/"
    )
    
    # Return UserResponse with token explicitly for clients that can't read cookies (Safari)
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        access_token=session_token
    )

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

@router.post("/invite", response_model=UserResponse)
def invite_user(invite_data: InviteRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Check if user exists
    existing = crud_user.user.get_by_email(db, email=invite_data.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
        
    # Create User (Pending)
    # We set a random password initially (unusable)
    random_pw = secrets.token_urlsafe(16)
    user_in = User(
        email=invite_data.email,
        hashed_password=crud_user.user.get_password_hash(random_pw), # Or use dummy
        full_name=invite_data.full_name,
        is_active=True, # Active but not verified? Or False? Requirements say invite-only. Usually pending=True.
        # Let's set is_active=True so they can login AFTER set password.
        is_verified=False,
        email_verified_at=None
    )
    db.add(user_in)
    db.commit()
    db.refresh(user_in)
    
    # Create Token
    token_str = secrets.token_urlsafe(32)
    token_hash = get_session_token_hash(token_str)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    
    ver_token = VerificationToken(
        user_id=user_in.id,
        token_hash=token_hash,
        expires_at=expires_at
    )
    db.add(ver_token)
    db.commit()
    
    # Send Email
    email_service.send_verification_email(user_in.email, token_str)
    
    return user_in

@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    token_hash = get_session_token_hash(token)
    
    ver_token = db.query(VerificationToken).filter(VerificationToken.token_hash == token_hash).first()
    
    error_redirect = f"{settings.CORS_ORIGINS[0]}/login?error=invalid_token" # Fallback
    # Ideally use APP_BASE_URL env if available, or just use first CORS origin as heuristic
    base_url = settings.ENVIRONMENT == 'production' and "https://<vercel-domain>" or "http://localhost:5173"
    # Actually, email_service uses APP_BASE_URL. We should use that logic or import it.
    # But for redirects, simple is better.
    # Let's assume CORS_ORIGINS[0] is frontend.
    
    if not ver_token:
        # Invalid token
        raise HTTPException(status_code=400, detail="Invalid token")
        
    # Check expiry
    if ver_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token expired")
        
    if ver_token.used_at:
         raise HTTPException(status_code=400, detail="Token already used")

    # Mark user verified
    user = db.query(User).filter(User.id == ver_token.user_id).first()
    if user:
        user.email_verified_at = datetime.now(timezone.utc)
        user.is_verified = True
        db.add(user)
        # Note: We do NOT mark token used here, so SetPassword can consume it.
        # ver_token.used_at = datetime.now(timezone.utc)
        # db.add(ver_token)
        db.commit()
    
    # Return JSON success
    return {"message": "Email verified successfully", "token": token}

@router.post("/set-password")
def set_password(payload: SetPasswordRequest, db: Session = Depends(get_db)):
    token_hash = get_session_token_hash(payload.token)
    ver_token = db.query(VerificationToken).filter(VerificationToken.token_hash == token_hash).first()
    
    if not ver_token:
        raise HTTPException(status_code=400, detail="Invalid token")
        
    # Expiry check
    if ver_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token expired")
    
    # Check if used
    if ver_token.used_at:
        raise HTTPException(status_code=400, detail="Token already used")
    
    user = db.query(User).filter(User.id == ver_token.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Set password
    user.hashed_password = crud_user.user.get_password_hash(payload.password)
    user.is_active = True # Activate
    user.email_verified_at = datetime.now(timezone.utc) # Ensure verified
    user.is_verified = True
    
    # Consume token
    ver_token.used_at = datetime.now(timezone.utc)
    db.add(ver_token)
    
    db.add(user)
    db.commit()
    
    return {"message": "Password set successfully"}

@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    # Always return 200 to prevent user enumeration
    user = crud_user.user.get_by_email(db, email=payload.email)
    if user and user.is_active:
        # Create Reset Token
        token_str = secrets.token_urlsafe(32)
        token_hash = get_session_token_hash(token_str)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at
        )
        db.add(reset_token)
        db.commit()
        
        # Send Email
        email_service.send_password_reset_email(user.email, token_str)
        
    return {"message": "If the email exists, a reset link has been sent."}

@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_hash = get_session_token_hash(payload.token)
    reset_token = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_hash).first()
    
    if not reset_token:
        raise HTTPException(status_code=400, detail="Invalid token")
        
    if reset_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token expired")
        
    if reset_token.used_at:
        raise HTTPException(status_code=400, detail="Token already used")
        
    user = db.query(User).filter(User.id == reset_token.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Set new password
    user.hashed_password = crud_user.user.get_password_hash(payload.password)
    
    # Mark used
    reset_token.used_at = datetime.now(timezone.utc)
    db.add(reset_token)
    
    # Optional: Revoke all existing sessions
    db.query(RefreshSession).filter(RefreshSession.user_id == user.id).delete()
    
    db.add(user)
    db.commit()
    
    return {"message": "Password reset successfully"}

@router.post("/request-access")
def request_access(payload: InviteRequest, db: Session = Depends(get_db)):
    # 1. Check if user already exists
    existing = crud_user.user.get_by_email(db, email=payload.email)
    if existing:
        # If user exists, we don't need to do anything, or maybe notify them "You have an account"
        # For security/privacy, we can just say "Request received"
        pass
    
    # 2. Send Email to Admin
    email_service.send_access_request_email(payload.email)
    
    return {"message": "Request received"}

