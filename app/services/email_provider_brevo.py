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

    def _send_html_email(self, *, to_email: str, subject: str, html_content: str) -> bool:
        if not self.is_configured():
            logger.info(
                "[Mock Email] to=%s subject=%s\n--- EMAIL HTML START ---\n%s\n--- EMAIL HTML END ---",
                to_email,
                subject,
                html_content,
            )
            return True

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
            return True
        except httpx.HTTPStatusError as e:
            logger.error("Brevo API error status=%s body=%s", e.response.status_code, e.response.text)
            return False
        except Exception as e:
            logger.error("Brevo send failed: %s", str(e))
            return False

    def send_html_email(self, to_email: str, subject: str, html_content: str) -> bool:
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
