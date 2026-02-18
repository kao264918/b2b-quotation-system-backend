import html
import logging

from app.config import settings
from app.services.email_provider_brevo import BrevoEmailProvider
from app.database import SessionLocal
from app.models.email_log import EmailLog, EmailStatus

logger = logging.getLogger(__name__)


def _record_email_log(recipient: str, email_type: str, success: bool, message_id: str | None, error: str | None):
    """Record email send result to DB. Uses its own session (for background tasks)."""
    try:
        db = SessionLocal()
        log = EmailLog(
            recipient=recipient,
            email_type=email_type,
            status=EmailStatus.MOCKED if message_id == "mock" else (EmailStatus.SUCCESS if success else EmailStatus.FAILED),
            provider_message_id=message_id if message_id != "mock" else None,
            error_reason=error,
        )
        db.add(log)
        db.commit()
        db.close()
    except Exception as e:
        logger.error("Failed to record email log: %s", str(e))


class EmailService:
    def __init__(self):
        self._provider = BrevoEmailProvider()
        if not self._provider.is_configured():
            logger.warning(
                "Brevo email is not configured (missing one of BREVO_API_KEY/BREVO_SENDER_EMAIL/BREVO_SENDER_NAME). "
                "Emails will be mocked in logs."
            )

    def send_verification_email(self, email: str, token: str) -> bool:
        verify_url = f"{settings.APP_BASE_URL}/verify-email?token={token}"
        success, msg_id, error = self._provider.send_verify_email(email, verify_url)
        _record_email_log(email, "verify", success, msg_id, error)
        return success

    def send_password_reset_email(self, email: str, token: str) -> bool:
        reset_url = f"{settings.APP_BASE_URL}/reset-password?token={token}"
        success, msg_id, error = self._provider.send_reset_password_email(email, reset_url)
        _record_email_log(email, "reset_password", success, msg_id, error)
        return success

    def send_access_request_email(self, user_email: str, full_name: str = None, company_name: str = None, note: str = None) -> bool:
        # Send TO all configured admin emails
        admin_emails = settings.ADMIN_NOTIFICATION_EMAILS or []
        
        # Fallback to sender email if no admin emails configured
        if not admin_emails:
            fallback_email = (settings.BREVO_SENDER_EMAIL or "").strip()
            if fallback_email:
                admin_emails = [fallback_email]
        
        if not admin_emails:
            logger.info(
                "[Mock Email] No admin recipients configured (ADMIN_NOTIFICATION_EMAILS or BREVO_SENDER_EMAIL). "
                "Would notify admin about access request from=%s",
                user_email,
            )
            _record_email_log(user_email, "access_request", True, "mock", None)
            return True
        
        # Send to all admin emails
        overall_success = True
        for admin_email in admin_emails:
            success, msg_id, error = self._provider.send_access_request_notification(
                admin_email, user_email, full_name, company_name, note
            )
            _record_email_log(admin_email, "access_request", success, msg_id, error)
            if not success:
                overall_success = False
                logger.error(f"Failed to send access request notification to {admin_email}")
        
        return overall_success

    def send_welcome_email(self, email: str, token: str) -> bool:
        # Token purpose=account_setup
        setup_url = f"{settings.APP_BASE_URL}/reset-password?token={token}"
        success, msg_id, error = self._provider.send_welcome_setup_email(email, setup_url)
        _record_email_log(email, "welcome", success, msg_id, error)
        return success

    def send_rejection_email(self, email: str, reason: str = None) -> bool:
        success, msg_id, error = self._provider.send_rejection_email(email, reason)
        _record_email_log(email, "rejection", success, msg_id, error)
        return success

email_service = EmailService()
