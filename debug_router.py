import sys
print(f"Python path: {sys.path}")
try:
    from app.models.user import User, UserStatus
    print("Success importing app.models.user")
except Exception as e:
    print(f"Error importing app.models.user: {e}")

try:
    from app.models.token import VerificationToken
    print("Success importing app.models.token")
except Exception as e:
    print(f"Error importing app.models.token: {e}")

try:
    from app.core.security import get_session_token_hash
    print("Success importing app.core.security")
except Exception as e:
    print(f"Error importing app.core.security: {e}")

try:
    from app.database import get_db
    print("Success importing app.database")
except Exception as e:
    print(f"Error importing app.database: {e}")

try:
    from app.routers import auth
    print("Success importing app.routers.auth")
except Exception as e:
    print(f"Error importing app.routers.auth: {e}")

try:
    from app.main import app
    print("Success importing app.main")
except Exception as e:
    print(f"Error importing app.main: {e}")
