import logging
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


BREVO_SEND_EMAIL_URL = "https://api.brevo.com/v3/smtp/email"


@dataclass(frozen=True)
class BrevoSender:
    email: str
    name: str


class BrevoEmailProvider:
    """
    Thin adapter around Brevo Transactional Email API.

    Spec-required methods:
    - send_verify_email(to_email, verify_url)
    - send_reset_password_email(to_email, reset_url)
    """

    def __init__(self) -> None:
        self._api_key = (settings.BREVO_API_KEY or "").strip()
        self._sender_email = (settings.BREVO_SENDER_EMAIL or "").strip()
        self._sender_name = (settings.BREVO_SENDER_NAME or "").strip()

    def is_configured(self) -> bool:
        return bool(self._api_key and self._sender_email and self._sender_name)

    def _send_html_email(self, *, to_email: str, subject: str, html_content: str) -> tuple[bool, str | None, str | None]:
        """Returns (success, message_id, error_reason)"""
        if not self.is_configured():
            logger.info(
                "[Mock Email] to=%s subject=%s\n--- EMAIL HTML START ---\n%s\n--- EMAIL HTML END ---",
                to_email,
                subject,
                html_content,
            )
            return (True, "mock", None)

        headers = {
            "accept": "application/json",
            "api-key": self._api_key,
            "content-type": "application/json",
        }
        payload = {
            "sender": {"name": self._sender_name, "email": self._sender_email},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html_content,
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(BREVO_SEND_EMAIL_URL, headers=headers, json=payload)
                resp.raise_for_status()

            # Brevo typically returns {"messageId": "..."} on success.
            try:
                message_id = resp.json().get("messageId")
            except Exception:
                message_id = None

            logger.info("Brevo email sent to=%s subject=%s messageId=%s", to_email, subject, message_id)
            return (True, message_id, None)
        except httpx.HTTPStatusError as e:
            error = f"HTTP {e.response.status_code}: {e.response.text}"
            logger.error("Brevo API error status=%s body=%s", e.response.status_code, e.response.text)
            return (False, None, error)
        except Exception as e:
            error = str(e)
            logger.error("Brevo send failed: %s", error)
            return (False, None, error)

    def send_html_email(self, to_email: str, subject: str, html_content: str) -> tuple[bool, str | None, str | None]:
        """Generic email sender (used for non-auth notifications like access requests)."""
        return self._send_html_email(to_email=to_email, subject=subject, html_content=html_content)

    def send_verify_email(self, to_email: str, verify_url: str) -> bool:
        subject = "請驗證您的 Email"
        html = f"""
<!DOCTYPE html>
<html>
  <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #111;">
    <div style="max-width: 600px; margin: 0 auto; padding: 24px;">
      <h2 style="margin: 0 0 16px;">請驗證您的 Email</h2>
      <p style="margin: 0 0 16px;">請點擊下方按鈕完成驗證：</p>
      <p style="margin: 0 0 16px;">
        <a href="{verify_url}" style="display: inline-block; background: #DC2626; color: #fff; text-decoration: none; padding: 12px 16px; border-radius: 8px;">
          驗證 Email
        </a>
      </p>
      <p style="margin: 0 0 8px;">或複製此連結至瀏覽器：</p>
      <p style="margin: 0 0 16px; word-break: break-all;">{verify_url}</p>
      <p style="margin: 24px 0 0; font-size: 12px; color: #666;">
        若您未發起此操作，請忽略此郵件。
      </p>
    </div>
  </body>
</html>
""".strip()
        return self._send_html_email(to_email=to_email, subject=subject, html_content=html)

    def send_reset_password_email(self, to_email: str, reset_url: str) -> bool:
        subject = "重設密碼連結"
        html = f"""
<!DOCTYPE html>
<html>
  <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #111;">
    <div style="max-width: 600px; margin: 0 auto; padding: 24px;">
      <h2 style="margin: 0 0 16px;">重設密碼</h2>
      <p style="margin: 0 0 16px;">請點擊下方按鈕重設您的密碼：</p>
      <p style="margin: 0 0 16px;">
        <a href="{reset_url}" style="display: inline-block; background: #DC2626; color: #fff; text-decoration: none; padding: 12px 16px; border-radius: 8px;">
          重設密碼
        </a>
      </p>
      <p style="margin: 0 0 8px;">或複製此連結至瀏覽器：</p>
      <p style="margin: 0 0 16px; word-break: break-all;">{reset_url}</p>
      <p style="margin: 24px 0 0; font-size: 12px; color: #666;">
        若您未發起此操作，請忽略此郵件。
      </p>
    </div>
  </body>
</html>
""".strip()
        return self._send_html_email(to_email=to_email, subject=subject, html_content=html)

    def send_access_request_notification(self, admin_email: str, requester_email: str, full_name: str = None, company_name: str = None, note: str = None) -> bool:
        subject = "New Access Request - B2B Quotation System"
        
        # Build detail rows
        detail_rows = f'<p style="margin: 0 0 8px;"><strong>Email：</strong>{requester_email}</p>'
        if full_name:
            detail_rows += f'<p style="margin: 0 0 8px;"><strong>姓名：</strong>{full_name}</p>'
        if company_name:
            detail_rows += f'<p style="margin: 0 0 8px;"><strong>公司名稱：</strong>{company_name}</p>'
        if note:
            detail_rows += f'<p style="margin: 0 0 8px;"><strong>備註：</strong>{note}</p>'
        
        html = f"""
<!DOCTYPE html>
<html>
  <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #111;">
    <div style="max-width: 600px; margin: 0 auto; padding: 24px;">
      <h2 style="margin: 0 0 16px;">New Access Request</h2>
      <p style="margin: 0 0 16px;">A new user has requested access to the platform.</p>
      <div style="background: #f9f9f9; padding: 16px; border-radius: 8px; margin-bottom: 24px;">
        {detail_rows}
      </div>
      <p style="margin: 0 0 16px;">Please log in to the admin panel to review this request.</p>
    </div>
  </body>
</html>
""".strip()
        return self._send_html_email(to_email=admin_email, subject=subject, html_content=html)

    def send_welcome_setup_email(self, to_email: str, setup_url: str) -> bool:
        subject = "Welcome! Set up your password"
        html = f"""
<!DOCTYPE html>
<html>
  <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #111;">
    <div style="max-width: 600px; margin: 0 auto; padding: 24px;">
      <h2 style="margin: 0 0 16px;">Welcome to the Team</h2>
      <p style="margin: 0 0 16px;">Your account has been created. Please set up your password to continue:</p>
      <p style="margin: 0 0 16px;">
        <a href="{setup_url}" style="display: inline-block; background: #DC2626; color: #fff; text-decoration: none; padding: 12px 16px; border-radius: 8px;">
          Set Password
        </a>
      </p>
      <p style="margin: 0 0 8px;">Or copy this link to your browser:</p>
      <p style="margin: 0 0 16px; word-break: break-all;">{setup_url}</p>
    </div>
  </body>
</html>
""".strip()
        return self._send_html_email(to_email=to_email, subject=subject, html_content=html)

    def send_rejection_email(self, to_email: str, reason: str = None) -> bool:
        subject = "Update on your Access Request"
        if reason:
             reason_html = f"<p><strong>Reason:</strong> {reason}</p>"
        else:
             reason_html = ""
             
        html = f"""
<!DOCTYPE html>
<html>
  <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #111;">
    <div style="max-width: 600px; margin: 0 auto; padding: 24px;">
      <h2 style="margin: 0 0 16px;">Access Request Update</h2>
      <p style="margin: 0 0 16px;">Thank you for your interest. Unfortunately, your request for access has been declined at this time.</p>
      {reason_html}
    </div>
  </body>
</html>
""".strip()
        return self._send_html_email(to_email=to_email, subject=subject, html_content=html)
