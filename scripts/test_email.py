import sys
import os

# Ensure app can be imported
sys.path.append(os.getcwd())

from app.services.email import email_service
from app.config import settings

def test_send():
    print(f"Testing Brevo Email...")
    print(f"API Key present: {bool(settings.BREVO_API_KEY)}")
    print(f"Sender: {settings.BREVO_SENDER_NAME} <{settings.BREVO_SENDER_EMAIL}>")
    
    target_email = settings.BREVO_SENDER_EMAIL # Send to self for testing
    
    print(f"Sending test email to {target_email}...")
    success = email_service._send_email(
        target_email, 
        "Brevo Integration Test", 
        "<h1>It Works!</h1><p>This is a test email from the B2B Quotation System backend.</p>"
    )
    
    if success:
        print("✅ Email sent successfully!")
    else:
        print("❌ Email failed to send.")

if __name__ == "__main__":
    test_send()
