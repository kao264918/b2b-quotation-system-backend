"""Auth router for login/logout/me endpoints"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.models.user import User
from app.core.security import verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str | None
    role: str
    is_active: bool
    
    class Config:
        from_attributes = True


@router.post("/login")
async def login(request: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """Login endpoint - sets httpOnly cookie"""
    user = db.query(User).filter(User.email == request.email).first()
    
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )
    
    # Set session cookie (simplified - in production use JWT or secure session)
    max_age = 30 * 24 * 60 * 60 if request.remember_me else 24 * 60 * 60  # 30 days or 1 day
    response.set_cookie(
        key="session_user_id",
        value=str(user.id),
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=max_age
    )
    
    return {"user": UserResponse.model_validate(user)}


@router.get("/me", response_model=UserResponse)
async def get_current_user(response: Response, db: Session = Depends(get_db), session_user_id: str | None = None):
    """Get current logged in user from session cookie"""
    from fastapi import Request
    # Note: This is a simplified version. In production, use proper middleware to extract cookie
    # For now, we'll get it from a dependency
    raise HTTPException(status_code=401, detail="Not authenticated")


@router.post("/logout")
async def logout(response: Response):
    """Logout - clear session cookie"""
    response.delete_cookie(key="session_user_id")
    return {"message": "Logged out successfully"}


@router.post("/forgot-password")
async def forgot_password(email: EmailStr = None, db: Session = Depends(get_db)):
    """Send password reset email (stub)"""
    # In production, this would send an actual email
    return {"message": "If the email exists, a reset link has been sent"}


@router.post("/reset-password")
async def reset_password(token: str, password: str, confirm_password: str):
    """Reset password with token (stub)"""
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    return {"message": "Password reset successfully"}


@router.post("/set-password")
async def set_password(token: str, password: str, confirm_password: str):
    """Set initial password after invite (stub)"""
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    return {"message": "Password set successfully"}


@router.get("/verify-email")
async def verify_email(token: str):
    """Verify email with token (stub)"""
    return {"message": "Email verified successfully"}


@router.post("/request-access")
async def request_access(email: EmailStr):
    """Request access to the system (stub)"""
    return {"message": "Access request submitted"}
