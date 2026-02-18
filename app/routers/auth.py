from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.auth import LoginRequest, UserResponse, InviteRequest, SetPasswordRequest, ForgotPasswordRequest, ResetPasswordRequest, VerifyTokenResponse
from app.crud import user as crud_user
from app.models.session import RefreshSession
from app.models.user import User
from app.models.token import VerificationToken, PasswordResetToken
from app.models.user_status import UserStatus, UserRole
from app.models.registration_request import RegistrationRequest, RegistrationStatus
from app.config import settings
from app.core.rate_limit import rate_limiter
from app.services.email import email_service
from datetime import datetime, timedelta, timezone
from fastapi.responses import RedirectResponse
import secrets
from app.deps.auth import get_current_user, get_session_token_hash
from app.crud import audit_log as crud_audit_log

router = APIRouter()


def resolve_cookie_policy(request: Request) -> tuple[bool, str]:
    """
    Auto-detect production environment based on request protocol.
    
    HTTPS requests → SameSite=None; Secure (for cross-origin Safari support)
    HTTP requests → SameSite=lax (for local development)
    
    This approach doesn't rely on ENVIRONMENT variable and works automatically.
    """
    is_https = request.url.scheme == "https"
    
    if is_https:
        # Production: HTTPS with cross-origin support for Safari
        return True, "none"
    else:
        # Development: HTTP with same-site only
        return False, "lax"


def set_csrf_cookie(response: Response, token: str, request: Request) -> None:
    cookie_secure, cookie_samesite = resolve_cookie_policy(request)

    response.set_cookie(
        key="csrf_token",
        value=token,
        httponly=False,
        samesite=cookie_samesite,
        secure=cookie_secure,
        path="/",
    )

from app.core.rate_limit import get_client_ip, require_rate_limit

@router.post("/login", response_model=UserResponse)
def login(
    login_data: LoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    client_ip = get_client_ip(request)
    require_rate_limit(f"login:ip:{client_ip}", limit=20, window_seconds=60)
    require_rate_limit(f"login:email:{login_data.email}", limit=10, window_seconds=60)

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
    
    # Check Status (New for MVP)
    from app.models.user_status import UserStatus
    if user.status == UserStatus.DISABLED:
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )
    # Allow PENDING_PASSWORD to login? No.
    if user.status == UserStatus.PENDING_PASSWORD:
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="PASSWORD_NOT_SET"
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
    
    cookie_secure, cookie_samesite = resolve_cookie_policy(request)

    response.set_cookie(
        key="session_id",
        value=session_token,
        httponly=True,
        max_age=session_duration_days * 24 * 60 * 60,
        expires=expires_at,
        samesite=cookie_samesite,
        secure=cookie_secure,
        path="/",
    )

    # CSRF token cookie (double-submit)
    csrf_token = secrets.token_urlsafe(32)
    set_csrf_cookie(response, csrf_token, request)

    # Session token is delivered via httpOnly cookie only.
    # Do NOT leak it in the response body (prevents JS/log interception).
    
    # Audit log for login
    crud_audit_log.log_action(
        db,
        entity_type="user",
        entity_id=str(user.id),
        action="login",
        actor=user.email,
        changes={"ip": client_ip},
    )
    
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        access_token=session_token if not settings.ENVIRONMENT == "production" else None,
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
    
    cookie_secure, cookie_samesite = resolve_cookie_policy(request)
    
    response.delete_cookie("session_id", path="/", samesite=cookie_samesite, secure=cookie_secure)
    response.delete_cookie("csrf_token", path="/", samesite=cookie_samesite, secure=cookie_secure)
    return {"message": "Logged out successfully"}

@router.get("/csrf")
def csrf_token(response: Response, request: Request):
    token = secrets.token_urlsafe(32)
    set_csrf_cookie(response, token, request)
    return {"csrf_token": token}

@router.post("/invite", response_model=UserResponse)
def invite_user(
    invite_data: InviteRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    require_rate_limit(f"invite:admin:{current_user.id}", limit=30, window_seconds=3600)
    
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
        email_verified_at=None,
        status=UserStatus.PENDING_PASSWORD,
        role=UserRole.MEMBER
    )
    db.add(user_in)
    db.commit()
    db.refresh(user_in)
    
    # Create Token
    token_str = secrets.token_urlsafe(32)
    token_hash = get_session_token_hash(token_str)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    
    ver_token = VerificationToken(
        user_id=user_in.id,
        token_hash=token_hash,
        expires_at=expires_at
    )
    db.add(ver_token)
    db.commit()
    
    # Send Email
    background_tasks.add_task(email_service.send_welcome_email, user_in.email, token_str)
    
    # Audit log for invite
    crud_audit_log.log_action(
        db,
        entity_type="user",
        entity_id=str(user_in.id),
        action="invite",
        actor=current_user.email,
    )
    
    return user_in

@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    token_hash = get_session_token_hash(token)
    
    ver_token = db.query(VerificationToken).filter(VerificationToken.token_hash == token_hash).first()
    
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
    
    # Return JSON success — never leak the token in the response body.
    # The frontend already has the token from the URL query parameter.
    return {"message": "Email verified successfully"}

@router.get("/verify-token-info", response_model=VerifyTokenResponse)
def verify_token_info(token: str, db: Session = Depends(get_db)):
    """
    Check if a token is valid (VerificationToken OR PasswordResetToken) and return associated user info.
    Used by frontend to decide if it needs to ask for full_name.
    """
    token_hash = get_session_token_hash(token)
    
    # 1. Check VerificationToken (Invite / Setup)
    ver_token = db.query(VerificationToken).filter(VerificationToken.token_hash == token_hash).first()
    if ver_token and ver_token.expires_at > datetime.now(timezone.utc):
        user = db.query(User).filter(User.id == ver_token.user_id).first()
        if user:
            return {
                "valid": True,
                "email": user.email,
                "full_name": user.full_name,
                "is_verified": user.is_verified
            }

    # 2. Check PasswordResetToken (Forgot Password)
    reset_token = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_hash).first()
    if reset_token and reset_token.expires_at > datetime.now(timezone.utc) and not reset_token.used_at:
        user = db.query(User).filter(User.id == reset_token.user_id).first()
        if user:
            return {
                "valid": True,
                "email": user.email,
                "full_name": user.full_name,
                "is_verified": user.is_verified
            }
            
    return {"valid": False}


@router.post("/set-password")
def set_password(payload: SetPasswordRequest, db: Session = Depends(get_db)):
    # Legacy endpoint, kept for compatibility if needed, but email links now point to reset-password.
    # Logic similar to reset_password but only for VerificationToken.
    token_hash = get_session_token_hash(payload.token)
    ver_token = db.query(VerificationToken).filter(VerificationToken.token_hash == token_hash).first()
    
    if not ver_token:
        raise HTTPException(status_code=400, detail="Invalid token")
        
    if ver_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token expired")
    
    # Check if used - VerificationToken doesn't have used_at usually, it's deleted.
    # But if we added used_at, check it. The current model might not have used_at for VerificationToken.
    # We delete it on use.
    
    user = db.query(User).filter(User.id == ver_token.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.hashed_password = crud_user.user.get_password_hash(payload.password)
    user.is_verified = True
    user.email_verified_at = datetime.now(timezone.utc)
    if user.status == UserStatus.PENDING_PASSWORD:
        user.status = UserStatus.ACTIVE
        
    db.delete(ver_token)
    db.add(user)
    db.commit()
    
    return {"message": "Password set successfully"}

@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    client_ip = get_client_ip(request)
    require_rate_limit(f"forgot:ip:{client_ip}", limit=10, window_seconds=60)
    require_rate_limit(f"forgot:email:{payload.email}", limit=5, window_seconds=60)

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
        background_tasks.add_task(email_service.send_password_reset_email, user.email, token_str)
        
    return {"message": "If the email exists, a reset link has been sent."}

@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = get_client_ip(request)
    require_rate_limit(f"reset:ip:{client_ip}", limit=10, window_seconds=60)

    token_hash = get_session_token_hash(payload.token)
    
    # Try finding either token type
    ver_token = db.query(VerificationToken).filter(VerificationToken.token_hash == token_hash).first()
    reset_token = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_hash).first()
    
    target_token = None
    token_type = None # "verification" or "reset"
    
    if ver_token:
        # Check expiry for VerificationToken
        if ver_token.expires_at > datetime.now(timezone.utc):
            target_token = ver_token
            token_type = "verification"
    elif reset_token:
        # Check expiry and used status for PasswordResetToken
        if reset_token.expires_at > datetime.now(timezone.utc) and not reset_token.used_at:
            target_token = reset_token
            token_type = "reset"
            
    if not target_token:
        # If neither found or valid
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == target_token.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Set new password
    user.hashed_password = crud_user.user.get_password_hash(payload.password)
    
    # Activate / Verify if needed (Logic for Invite flow)
    # If user was PENDING_PASSWORD, they become ACTIVE
    if user.status == UserStatus.PENDING_PASSWORD:
        user.status = UserStatus.ACTIVE
    
    # Mark as verified if not already
    if not user.is_verified:
        user.is_verified = True
        user.email_verified_at = datetime.now(timezone.utc)

    # Update full_name if provided
    if payload.full_name:
        user.full_name = payload.full_name
    
    # Handle Token Cleanup
    if token_type == "verification":
        db.delete(target_token) # Destroy verification token
    else:
        # Mark reset token used
        target_token.used_at = datetime.now(timezone.utc)
        db.add(target_token)
        # Optional: Revoke all existing sessions
        db.query(RefreshSession).filter(RefreshSession.user_id == user.id).delete()
    
    db.add(user)
    db.commit()
    
    # Audit log for password reset
    crud_audit_log.log_action(
        db,
        entity_type="user",
        entity_id=str(user.id),
        action="reset_password",
        actor=user.email,
    )
    
    return {"message": "Password reset successfully"}

@router.post("/request-access")
def request_access(
    payload: InviteRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    client_ip = get_client_ip(request)
    require_rate_limit(f"request_access:ip:{client_ip}", limit=10, window_seconds=60)

    # 1. Check if user already exists
    existing = crud_user.user.get_by_email(db, email=payload.email)
    if existing:
        # If user exists, we don't need to do anything, or maybe notify them "You have an account"
        # For security/privacy, we can just say "Request received"
        return {"message": "Request received"}
    
    # 2. Persist Request to DB
    # Check if request already exists (any status)
    existing_request = db.query(RegistrationRequest).filter(
        RegistrationRequest.email == payload.email
    ).first()
    
    if existing_request:
        # Check if rejected within last 1 hour
        if existing_request.status == RegistrationStatus.REJECTED:
            # Ensure updated_at is aware or naive compatible. DB is timezone=True.
            last_update = existing_request.updated_at or existing_request.created_at
            if last_update:
                # If last_update is naive, make it aware (assume UTC if stored as such)
                if last_update.tzinfo is None:
                    last_update = last_update.replace(tzinfo=timezone.utc)
                
                if datetime.now(timezone.utc) - last_update < timedelta(hours=1):
                    raise HTTPException(
                        status_code=400, 
                        detail="您的申請已被拒絕，請於 1 小時後再嘗試。"
                    )

        existing_request.full_name = payload.full_name or ""
        existing_request.company_name = payload.company_name or ""
        existing_request.note = payload.note
        existing_request.status = RegistrationStatus.PENDING # Reset to pending if it was rejected/approved
        existing_request.updated_at = datetime.now(timezone.utc)
        db.commit()
    else:
        # Create new request
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

    # 3. Send Email to Admin
    background_tasks.add_task(
        email_service.send_access_request_email,
        payload.email,
        payload.full_name,
        payload.company_name,
        payload.note,
    )
    
    return {"message": "Request received"}


@router.post("/cleanup-sessions")
def cleanup_expired_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Remove all expired sessions from the database.
    Superuser only. Can be called by a cron job or admin manually.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    deleted = (
        db.query(RefreshSession)
        .filter(RefreshSession.expires_at < datetime.now(timezone.utc))
        .delete()
    )
    db.commit()
    return {"message": f"Cleaned up {deleted} expired sessions"}
