import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "B2B Quotation System"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/b2b_quotation"
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",           # Vite dev
        "http://localhost:5174",           # Vite dev (alternate port)
        "http://localhost:3000",           # Alternative dev
        "https://*.vercel.app",            # Vercel previews
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

settings = Settings()
