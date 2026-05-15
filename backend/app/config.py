"""Application configuration using Pydantic Settings."""

import os
from typing import List

from pydantic import Field, field_validator
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
    DATABASE_URL: str = Field(default="")
    
    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_url(cls, v: str) -> str:
        if v and v != "":
            return v
        # Try Railway DATABASE_URL
        db_url = os.environ.get("DATABASE_URL", "")
        if db_url:
            return db_url
        # Try Railway MYSQL_URL (convert mysql:// to mysql+aiomysql://)
        mysql_url = os.environ.get("MYSQL_URL", "")
        if mysql_url:
            return mysql_url.replace("mysql://", "mysql+aiomysql://", 1)
        # Try individual Railway MySQL env vars
        host = os.environ.get("MYSQLHOST", "localhost")
        port = os.environ.get("MYSQLPORT", "3306")
        user = os.environ.get("MYSQLUSER", "root")
        password = os.environ.get("MYSQLPASSWORD", "password")
        database = os.environ.get("MYSQLDATABASE", "ai_marketing")
        return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{database}"

    # Redis
    REDIS_URL: str = Field(default="")
    
    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def assemble_redis_url(cls, v: str) -> str:
        if v and v != "":
            return v
        # Try Railway Redis env vars
        redis_url = os.environ.get("REDIS_URL", "")
        if redis_url:
            return redis_url
        redis_public = os.environ.get("REDIS_PUBLIC_URL", "")
        if redis_public:
            return redis_public
        redis_private = os.environ.get("REDISPRIVATE_URL", "")
        if redis_private:
            return redis_private
        return "redis://localhost:6379/0"

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
