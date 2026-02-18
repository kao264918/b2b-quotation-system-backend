try:
    from app.schemas.auth import VerifyTokenResponse
    print("Success importing VerifyTokenResponse")
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")
