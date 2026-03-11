"""Quick test: send a welcome email directly via EmailService."""
import sys
sys.path.insert(0, ".")

from app.services.email import email_service

# Use a dummy token - we just want to verify Brevo sends the email
test_email = "user@example.com"
test_token = "test_resend_verification_token_12345"

print(f"Sending welcome email to {test_email}...")
result = email_service.send_welcome_email(test_email, test_token)
print(f"Result: {result}")
