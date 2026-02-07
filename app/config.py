from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "B2B Quotation System"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"  # development | production

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/b2b_quotation"

    # Auth / Security
    # NOTE: Must be overridden in production via environment variable.
    SECRET_KEY: str = "CHANGE_THIS_IN_PRODUCTION_SECRET_KEY"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # Access token duration (short lived)
    SESSION_EXPIRE_DAYS: int = 7           # Refresh session duration (long lived)

    # CORS
    # Tip: In .env provide JSON: CORS_ORIGINS=["http://localhost:5173","https://your-app.vercel.app"]
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
    ]

    # Vercel preview domain regex — restrict to YOUR project prefix only.
    # Matches preview hosts that include "b2b-quotation-system" in a single hostname label.
    # Override via env var CORS_ORIGIN_REGEX in production for stricter control.
    CORS_ORIGIN_REGEX: Optional[str] = r"https://[a-z0-9-]*b2b-quotation-system[a-z0-9-]*\.vercel\.app"

    # Frontend base URL (used to construct email links)
    APP_BASE_URL: str = "http://localhost:5173"

    # Brevo (Transactional Email)
    # API key MUST come from environment variables (never hardcode a real key).
    BREVO_API_KEY: Optional[str] = None
    BREVO_SENDER_EMAIL: Optional[str] = None
    BREVO_SENDER_NAME: Optional[str] = None

    # Rate limiting (Redis)
    REDIS_URL: Optional[str] = None

    # Error tracking (Sentry)
    SENTRY_DSN: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
