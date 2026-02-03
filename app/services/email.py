import logging

from app.config import settings
from app.services.email_provider_brevo import BrevoEmailProvider

logger = logging.getLogger(__name__)

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
        return self._provider.send_verify_email(email, verify_url)

    def send_password_reset_email(self, email: str, token: str) -> bool:
        reset_url = f"{settings.APP_BASE_URL}/reset-password?token={token}"
        return self._provider.send_reset_password_email(email, reset_url)

    def send_access_request_email(self, user_email: str) -> bool:
        subject = "New Access Request - B2B Quotation System"
        content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>New Access Request</h2>
                <p>A new user has requested access to the platform.</p>
                <p><strong>Email:</strong> {user_email}</p>
                <hr>
                <p style="font-size: 12px; color: #666;">
                    To approve this user, please use the admin invite functionality or run the invite script locally.
                </p>
            </div>
        </body>
        </html>
        """
        # Send TO the admin (sender_email). If not configured, fall back to logging.
        admin_email = (settings.BREVO_SENDER_EMAIL or "").strip()
        if not admin_email:
            logger.info(
                "[Mock Email] Admin recipient missing (BREVO_SENDER_EMAIL). "
                "Would notify admin about access request from=%s",
                user_email,
            )
            return True

        return self._provider.send_html_email(admin_email, subject, content)

email_service = EmailService()
