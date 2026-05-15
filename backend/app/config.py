"""Application configuration using Pydantic Settings."""

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = Field(default="AI Marketing Platform")
    DEBUG: bool = Field(default=False)
    ALLOWED_ORIGINS: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:5173",
            "https://*.railway.app",
            "https://*.up.railway.app",
        ]
    )

    # Database
    DATABASE_URL: str = Field(
        default="mysql+aiomysql://root:password@localhost:3306/ai_marketing"
    )

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # JWT
    JWT_SECRET_KEY: str = Field(default="super-secret-jwt-key-change-in-production")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_HOURS: int = Field(default=24)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)

    # Encryption
    SECRET_KEY: str = Field(default="super-secret-encryption-key-change-in-production")

    # Celery
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/2")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
