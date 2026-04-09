import json
from typing import Annotated, List, Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_CORS_ORIGIN_REGEX = r"^https://([a-z0-9-]+-)?b2b-quotation-system\.vercel\.app$"



class Settings(BaseSettings):
    PROJECT_NAME: str = "B2B Quotation System"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"  # development | production

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/b2b_quotation"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 300

    # Auth / Security
    # NOTE: Must be overridden in production via environment variable.
    SECRET_KEY: str = "CHANGE_THIS_IN_PRODUCTION_SECRET_KEY"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # Access token duration (short lived)
    SESSION_EXPIRE_DAYS: int = 7           # Refresh session duration (long lived)

    # CORS
    # Tip: In .env provide JSON: CORS_ORIGINS=["http://localhost:5173","https://your-app.vercel.app"]
    CORS_ORIGINS: Annotated[List[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
    ]

    # Vercel preview domain regex — restrict to b2b-quotation-system project host only.
    # Expected host examples:
    # - b2b-quotation-system.vercel.app
    # - dev-b2b-quotation-system.vercel.app
    # - feat-123-b2b-quotation-system.vercel.app
    CORS_ORIGIN_REGEX: Optional[str] = DEFAULT_CORS_ORIGIN_REGEX
    # Backward compatibility for a common typo in env var name.
    # If this is set and CORS_ORIGIN_REGEX isn't explicitly overridden, it will be used.
    CORS_ORIGINS_REGEX: Optional[str] = None

    # Frontend base URL (used to construct email links)
    APP_BASE_URL: str = "http://localhost:5173"

    # Brevo (Transactional Email)
    # API key MUST come from environment variables (never hardcode a real key).
    BREVO_API_KEY: Optional[str] = None
    BREVO_SENDER_EMAIL: Optional[str] = None
    BREVO_SENDER_NAME: Optional[str] = None
    
    # Admin notification emails for access requests (JSON array)
    ADMIN_NOTIFICATION_EMAILS: Annotated[List[str], NoDecode] = []

    # Rate limiting (Redis)
    REDIS_URL: Optional[str] = None

    # Error tracking (Sentry)
    SENTRY_DSN: Optional[str] = None

    # Logging
    REQUEST_LOG_SLOW_MS: int = 1000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if value is None:
            return []

        if isinstance(value, list):
            return [str(origin).rstrip("/") for origin in value if str(origin).strip()]

        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []

            # Prefer JSON array, but also accept comma-separated string
            # to reduce config mistakes on Railway/Vercel.
            if raw.startswith("["):
                parsed = json.loads(raw)
                if not isinstance(parsed, list):
                    raise ValueError("CORS_ORIGINS JSON must be an array")
                return [str(origin).rstrip("/") for origin in parsed if str(origin).strip()]

            return [part.strip().rstrip("/") for part in raw.split(",") if part.strip()]

        raise ValueError("Invalid CORS_ORIGINS format")

    @field_validator("APP_BASE_URL", mode="before")
    @classmethod
    def normalize_app_base_url(cls, value):
        if isinstance(value, str):
            return value.rstrip("/")
        return value
    
    @field_validator("ADMIN_NOTIFICATION_EMAILS", mode="before")
    @classmethod
    def parse_admin_emails(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [str(email).strip() for email in value if str(email).strip()]
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            # JSON array format
            if raw.startswith("["):
                parsed = json.loads(raw)
                if not isinstance(parsed, list):
                    raise ValueError("ADMIN_NOTIFICATION_EMAILS must be an array")
                return [str(email).strip() for email in parsed if str(email).strip()]
            # Comma-separated fallback
            return [str(email).strip() for email in raw.split(",") if email.strip()]
        raise ValueError(f"ADMIN_NOTIFICATION_EMAILS: unsupported type {type(value)}")

    @model_validator(mode="after")
    def apply_legacy_cors_regex_alias(self):
        if (
            self.CORS_ORIGINS_REGEX
            and (not self.CORS_ORIGIN_REGEX or self.CORS_ORIGIN_REGEX == DEFAULT_CORS_ORIGIN_REGEX)
        ):
            self.CORS_ORIGIN_REGEX = self.CORS_ORIGINS_REGEX
        return self


settings = Settings()
