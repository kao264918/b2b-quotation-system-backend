import os
import logging
import httpx
from typing import List, Dict, Any
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.api_key = settings.BREVO_API_KEY
        self.sender_email = settings.BREVO_SENDER_EMAIL
        self.sender_name = settings.BREVO_SENDER_NAME
        self.app_base_url = os.getenv("APP_BASE_URL", "http://localhost:5173") # Or from settings if we added it there
        
        if not self.api_key:
            logger.warning("BREVO_API_KEY is not set. Emails will NOT be sent.")

    def _send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """
        Sends an email using Brevo (Sendinblue) Transactional Email API v3.
        """
        if not self.api_key:
            logger.info(f"[Mock Email] To: {to_email}, Subject: {subject}\n--- EMAIL CONTENT START ---\n{html_content}\n--- EMAIL CONTENT END ---")
            return True

        url = "https://api.brevo.com/v3/smtp/email"
        headers = {
            "accept": "application/json",
            "api-key": self.api_key,
            "content-type": "application/json"
        }
        
        payload = {
            "sender": {
                "name": self.sender_name,
                "email": self.sender_email
            },
            "to": [
                {
                    "email": to_email
                }
            ],
            "subject": subject,
            "htmlContent": html_content
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                logger.info(f"Email sent to {to_email}. Message ID: {response.json().get('messageId')}")
                return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Brevo API HTTP Error: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False

    def send_verification_email(self, email: str, token: str) -> bool:
        # In production, ensure APP_BASE_URL is correct in .env
        verify_url = f"{self.app_base_url}/verify-email?token={token}"
        subject = "請驗證您的 B2B Quotation System 帳號"
        content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .button {{ display: inline-block; padding: 10px 20px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px; margin-top: 20px; }}
                .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>歡迎使用 B2B Quotation System</h2>
                <p>您好，</p>
                <p>請點擊下方連結以驗證您的電子郵件並啟用帳號：</p>
                <p>
                    <a href="{verify_url}" class="button">驗證電子郵件</a>
                </p>
                <p>或複製此連結至瀏覽器：<br>{verify_url}</p>
                <p>此連結將在 24 小時後失效。</p>
                <div class="footer">
                    <p>如果這不是您要求的，請忽略此郵件。</p>
                </div>
            </div>
        </body>
        </html>
        """
        return self._send_email(email, subject, content)

    def send_password_reset_email(self, email: str, token: str) -> bool:
        reset_url = f"{self.app_base_url}/reset-password?token={token}"
        subject = "重設您的密碼 - B2B Quotation System"
        content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .button {{ display: inline-block; padding: 10px 20px; background-color: #dc3545; color: white; text-decoration: none; border-radius: 5px; margin-top: 20px; }}
                .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>重設密碼請求</h2>
                <p>您好，</p>
                <p>我們收到了一個重設您帳號密碼的請求。</p>
                <p>若這不是您本人的操作，請忽略此郵件。</p>
                <p>
                    <a href="{reset_url}" class="button">重設密碼</a>
                </p>
                <p>或複製此連結至瀏覽器：<br>{reset_url}</p>
                <p>此連結將在 1 小時後失效。</p>
            </div>
        </body>
        </html>
        """
        return self._send_email(email, subject, content)

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
        # Send TO the admin (sender_email)
        return self._send_email(self.sender_email, subject, content)

email_service = EmailService()
