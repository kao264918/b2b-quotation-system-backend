from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database import get_db
from app.models.registration_request import RegistrationRequest, RegistrationStatus
from app.models.user import User
from app.models.user_status import UserStatus, UserRole
from app.models.token import VerificationToken
from app.schemas.registration import RegistrationRequestCreate, RegistrationRequestResponse, RegistrationApproveRequest, RegistrationRejectRequest
from app.deps.auth import get_current_user, require_superuser, get_session_token_hash
from app.core.rate_limit import get_client_ip, require_rate_limit
from app.services.email import email_service
from app.crud import audit_log as crud_audit_log
import secrets
from datetime import datetime, timedelta, timezone
from app.crud import user as crud_user
import traceback

router = APIRouter()

# Public Endpoint
@router.post("/registration-requests", status_code=status.HTTP_202_ACCEPTED)
def create_registration_request(
    payload: RegistrationRequestCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # 1. Check if user already exists
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        # Prevent enumeration: return 202 as if successful
        return {"message": "Request received"}

    # 2. Check if request already exists (pending)
    existing_request = db.query(RegistrationRequest).filter(
        RegistrationRequest.email == payload.email,
        RegistrationRequest.status == RegistrationStatus.PENDING
    ).first()
    
    if existing_request:
        existing_request.updated_at = datetime.now(timezone.utc)
        db.commit()
    else:
        # Create new request
        new_request = RegistrationRequest(
            email=payload.email,
            full_name=payload.full_name,
            company_name=payload.company_name,
            note=payload.note,
            status=RegistrationStatus.PENDING
        )
        db.add(new_request)
        db.commit()
        db.refresh(new_request)

    # 3. Notify Admin (Email)
    background_tasks.add_task(
        email_service.send_access_request_email,
        payload.email,
        payload.full_name,
        payload.company_name,
        payload.note
    )
    
    return {"message": "Request received"}

# Admin: List all registration requests
@router.get("/admin/registration-requests", response_model=List[RegistrationRequestResponse])
def list_registration_requests(
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    requests = db.query(RegistrationRequest).order_by(RegistrationRequest.created_at.desc()).all()
    return requests


@router.post("/admin/registration-requests/{request_id}/approve")
def approve_registration_request(
    request_id: UUID,
    payload: RegistrationApproveRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    # ... (approval logic same as before)
    # 1. Get Request
    req = db.query(RegistrationRequest).filter(RegistrationRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if req.status != RegistrationStatus.PENDING:
        raise HTTPException(status_code=400, detail="Request is not pending")
        
    # 2. Check if user already exists (double check)
    if db.query(User).filter(User.email == req.email).first():
        req.status = RegistrationStatus.REJECTED # User exists, so invalidate request
        db.commit()
        raise HTTPException(status_code=400, detail="User already exists")

    # 3. Create User (Pending Password)
    random_pw = secrets.token_urlsafe(16)
    new_user = User(
        email=req.email,
        full_name=req.full_name,
        company_name=req.company_name,
        hashed_password=crud_user.user.get_password_hash(random_pw),
        status=UserStatus.PENDING_PASSWORD,
        role=UserRole(payload.role) if payload.role else UserRole.OWNER,
        is_active=True,
        is_verified=False
    )
    db.add(new_user)
    db.flush() # Generate ID for new_user
    db.refresh(new_user)
    
    # 4. Create Token (Account Setup)
    token_str = secrets.token_urlsafe(32)
    token_hash = get_session_token_hash(token_str)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24) 
    
    ver_token = VerificationToken(
        user_id=new_user.id,
        token_hash=token_hash,
        expires_at=expires_at
    )
    db.add(ver_token)
    
    # 5. Update Request Status
    req.status = RegistrationStatus.APPROVED
    
    db.commit()
    
    # 6. Send Email
    background_tasks.add_task(email_service.send_welcome_email, new_user.email, token_str)
    
    # 7. Audit Log
    crud_audit_log.log_action(
        db,
        entity_type="registration_request",
        entity_id=str(req.id),
        action="approve",
        actor=current_user.email,
        changes={"user_created": str(new_user.id)}
    )

    return {"message": "Request approved and user created"}

@router.post("/admin/registration-requests/{request_id}/reject")
def reject_registration_request(
    request_id: UUID,
    payload: RegistrationRejectRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    req = db.query(RegistrationRequest).filter(RegistrationRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
        
    if req.status != RegistrationStatus.PENDING:
        raise HTTPException(status_code=400, detail="Request is not pending")
        
    req.status = RegistrationStatus.REJECTED
    db.commit()
    
    background_tasks.add_task(email_service.send_rejection_email, req.email, payload.reason)
    
    crud_audit_log.log_action(
        db,
        entity_type="registration_request",
        entity_id=str(req.id),
        action="reject",
        actor=current_user.email,
        changes={"reason": payload.reason}
    )
    
    return {"message": "Request rejected"}


@router.post("/admin/registration-requests/{request_id}/resend-invitation")
def resend_invitation(
    request_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    # Server-side rate limiting
    client_ip = get_client_ip(request)
    require_rate_limit(f"resend-invite:{request_id}", limit=1, window_seconds=30)
    require_rate_limit(f"resend-invite:ip:{client_ip}", limit=20, window_seconds=600)

    req = db.query(RegistrationRequest).filter(RegistrationRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
        
    if req.status != RegistrationStatus.APPROVED:
        raise HTTPException(status_code=400, detail="Request is not in APPROVED status")
        
    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user.status != UserStatus.PENDING_PASSWORD:
        raise HTTPException(status_code=400, detail="User is already active or disabled")

    # Token lifecycle: revoke all existing tokens for this user before issuing new one
    db.query(VerificationToken).filter(VerificationToken.user_id == user.id).delete()
        
    # Generate NEW token
    token_str = secrets.token_urlsafe(32)
    token_hash = get_session_token_hash(token_str)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1) 
    
    ver_token = VerificationToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at
    )
    db.add(ver_token)
    db.commit()
    
    # Send Email
    background_tasks.add_task(email_service.send_welcome_email, user.email, token_str)
    
    return {"message": "Invitation resent successfully"}


# ============================================================
# Admin: Email Logs
# ============================================================
from app.models.email_log import EmailLog
from pydantic import BaseModel, ConfigDict
from typing import Optional

class EmailLogResponse(BaseModel):
    id: str
    recipient: str
    email_type: str
    status: str
    sent_at: Optional[str] = None
    provider_message_id: Optional[str] = None
    error_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

@router.get("/admin/email-logs/{email}")
def get_email_logs(
    email: str,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    logs = db.query(EmailLog).filter(
        EmailLog.recipient == email
    ).order_by(EmailLog.sent_at.desc()).limit(20).all()
    
    return [
        {
            "id": str(log.id),
            "recipient": log.recipient,
            "email_type": log.email_type,
            "status": log.status.name if log.status else None,
            "sent_at": log.sent_at.isoformat() if log.sent_at else None,
            "provider_message_id": log.provider_message_id,
            "error_reason": log.error_reason,
        }
        for log in logs
    ]

# ============================================================
# Admin: User Management
# ============================================================

from app.schemas.auth import AdminUserResponse, AdminUserUpdate

@router.get("/admin/users", response_model=List[AdminUserResponse])
def list_users(
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return users


@router.patch("/admin/users/{user_id}", response_model=AdminUserResponse)
def update_user(
    user_id: UUID,
    payload: AdminUserUpdate,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent self-demotion
    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot modify your own account")

    # Role-based permission checks
    if current_user.role == UserRole.ADMIN and not current_user.is_superuser:
        # Admin cannot modify owner
        if target.role == UserRole.OWNER:
            raise HTTPException(status_code=403, detail="Admin 無法修改 Owner")
        # Admin cannot promote anyone to owner
        if payload.role == "owner":
            raise HTTPException(status_code=403, detail="Admin 無法授予 Owner 權限")

    if payload.role is not None:
        new_role = UserRole(payload.role)
        # Guard: cannot demote the sole owner
        if target.role == UserRole.OWNER and new_role != UserRole.OWNER:
            owner_count = db.query(User).filter(User.role == UserRole.OWNER).count()
            if owner_count <= 1:
                raise HTTPException(
                    status_code=409,
                    detail="SOLE_OWNER_CANNOT_DEMOTE"
                )
        target.role = new_role
    if payload.status is not None:
        target.status = UserStatus(payload.status)
    if payload.is_superuser is not None:
        target.is_superuser = payload.is_superuser

    db.commit()
    db.refresh(target)

    crud_audit_log.log_action(
        db,
        entity_type="user",
        entity_id=str(target.id),
        action="update_role",
        actor=current_user.email,
        changes=payload.model_dump(exclude_none=True)
    )

    return target


@router.delete("/admin/users/{user_id}")
def delete_user(
    user_id: UUID,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent self-deletion
    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    # Cannot delete owner
    if target.role == UserRole.OWNER:
        raise HTTPException(status_code=403, detail="無法刪除 Owner，請先降級再刪除")

    # Manual Cleanup of related data (because DB cascade might be missing)
    try:
        # Delete related tokens first
        from app.models.token import VerificationToken, PasswordResetToken
        from app.models.session import RefreshSession
        
        db.query(VerificationToken).filter(VerificationToken.user_id == target.id).delete()
        db.query(PasswordResetToken).filter(PasswordResetToken.user_id == target.id).delete()
        db.query(RefreshSession).filter(RefreshSession.user_id == target.id).delete()
        
        db.delete(target)
        db.commit()
    except Exception as e:
        db.rollback()
        import traceback
        error_msg = f"Failed to delete user: {str(e)}"
        print(traceback.format_exc()) # Log to console
        raise HTTPException(status_code=400, detail=error_msg)

    crud_audit_log.log_action(
        db,
        entity_type="user",
        entity_id=str(target.id),
        action="delete",
        actor=current_user.email,
        changes={"deleted_user_email": target.email}
    )

    return {"message": "User deleted successfully"}


@router.post("/admin/users/{user_id}/reset-password-email")
def admin_trigger_reset_password(
    user_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
        
    if not target.is_active:
         raise HTTPException(status_code=400, detail="Cannot reset password for inactive user")

    # Create Reset Token
    token_str = secrets.token_urlsafe(32)
    token_hash = get_session_token_hash(token_str)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    
    # We need PasswordResetToken model
    from app.models.token import PasswordResetToken
    
    reset_token = PasswordResetToken(
        user_id=target.id,
        token_hash=token_hash,
        expires_at=expires_at
    )
    db.add(reset_token)
    db.commit()
    
    # Send Email
    background_tasks.add_task(email_service.send_password_reset_email, target.email, token_str)
    
    crud_audit_log.log_action(
        db,
        entity_type="user",
        entity_id=str(target.id),
        action="admin_trigger_reset",
        actor=current_user.email,
    )

    return {"message": f"Password reset email sent to {target.email}"}
