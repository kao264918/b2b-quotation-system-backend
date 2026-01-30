import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "B2B Quotation System"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/b2b_quotation"

    # Security
    SECRET_KEY: str = "CHANGE_THIS_TO_A_SECURE_RANDOM_STRING_IN_BPRODUCTION"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",           # Vite dev
        "http://localhost:5174",           # Vite dev (alternate port)
        "http://localhost:3000",           # Alternative dev
        "https://*.vercel.app",            # Vercel previews
    ]

    # Auth
    SECRET_KEY: str = "CHANGE_THIS_IN_PRODUCTION_SECRET_KEY"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # Access token duration (short lived)
    SESSION_EXPIRE_DAYS: int = 7           # Refresh session duration (long lived)
    
    # Brevo Email
    BREVO_API_KEY: str = ""
    BREVO_SENDER_EMAIL: str = "noreply@example.com"
    BREVO_SENDER_NAME: str = "B2B Quotation System"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
