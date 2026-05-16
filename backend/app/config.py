"""Application configuration using Pydantic Settings.

SECURITY NOTICE:
- JWT_SECRET_KEY and SECRET_KEY are REQUIRED at startup (fail-fast)
- Minimum 32 characters, high entropy, no default/placeholder values
- Both keys must be different (defense in depth)
- Generate secure keys with:
  python -c "import secrets; print(secrets.token_hex(32))"
"""

import os
from typing import ClassVar, List

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
            # Convert sync mysql:// to async mysql+aiomysql:// if needed
            if v.startswith("mysql://") and not v.startswith("mysql+aiomysql://"):
                return v.replace("mysql://", "mysql+aiomysql://", 1)
            return v
        # Try Railway DATABASE_URL
        db_url = os.environ.get("DATABASE_URL", "")
        if db_url:
            # Convert sync mysql:// to async mysql+aiomysql:// if needed
            if db_url.startswith("mysql://") and not db_url.startswith("mysql+aiomysql://"):
                return db_url.replace("mysql://", "mysql+aiomysql://", 1)
            return db_url
        # Try Railway MYSQL_URL (convert mysql:// to mysql+aiomysql://)
        mysql_url = os.environ.get("MYSQL_URL", "")
        if mysql_url:
            return mysql_url.replace("mysql://", "mysql+aiomysql://", 1)
        # Try individual Railway MySQL env vars
        host = os.environ.get("MYSQLHOST", "")
        if not host:
            raise ValueError("DATABASE_URL not configured. Set DATABASE_URL or Railway MySQL env vars.")
        port = os.environ.get("MYSQLPORT", "3306")
        user = os.environ.get("MYSQLUSER", "")
        password = os.environ.get("MYSQLPASSWORD", "")
        database = os.environ.get("MYSQLDATABASE", "")
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

    # ------------------------------------------------------------------
    # JWT - REQUIRED at startup (fail-fast if missing or weak)
    # ------------------------------------------------------------------
    JWT_SECRET_KEY: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_HOURS: int = Field(default=24)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)

    @field_validator("ACCESS_TOKEN_EXPIRE_HOURS")
    @classmethod
    def validate_access_token_ttl(cls, v: int) -> int:
        """Enforce reasonable access token expiry bounds."""
        if v < 1:
            raise ValueError(
                "ACCESS_TOKEN_EXPIRE_HOURS must be at least 1. "
                "Tokens shorter than 1 hour break usability."
            )
        if v > 168:
            raise ValueError(
                "ACCESS_TOKEN_EXPIRE_HOURS must not exceed 168 (7 days). "
                "Long-lived access tokens increase blast radius of a compromise."
            )
        return v

    @field_validator("REFRESH_TOKEN_EXPIRE_DAYS")
    @classmethod
    def validate_refresh_token_ttl(cls, v: int) -> int:
        """Enforce reasonable refresh token expiry bounds."""
        if v < 1:
            raise ValueError(
                "REFRESH_TOKEN_EXPIRE_DAYS must be at least 1. "
                "Shorter expiry forces excessive re-authentication."
            )
        if v > 30:
            raise ValueError(
                "REFRESH_TOKEN_EXPIRE_DAYS must not exceed 30. "
                "Long-lived refresh tokens increase the window for replay attacks."
            )
        return v

    # Encryption - REQUIRED at startup (fail-fast if missing)
    SECRET_KEY: str = Field(..., min_length=32)

    # Celery
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/2")

    # OpenAI API Key - Optional; graceful fallback when missing
    OPENAI_API_KEY: str = Field(default="")

    @field_validator("OPENAI_API_KEY", mode="before")
    @classmethod
    def validate_openai_api_key_format(cls, v: str) -> str:
        """Validate OpenAI API key format if provided.

        When empty, AI services operate in graceful fallback mode.
        When provided, it must start with 'sk-' to be a valid key.
        """
        if not v or v == "":
            return ""  # Graceful fallback: no API key = fallback mode
        if not v.startswith("sk-"):
            raise ValueError(
                "OPENAI_API_KEY must start with 'sk-'. "
                "Leave empty to enable graceful fallback mode."
            )
        return v

    # AI Supervised Mode - When True, all AI responses require human approval
    AI_SUPERVISED_MODE: bool = Field(default=True)

    # AI Usage Limits
    AI_MONTHLY_TOKEN_LIMIT: int = Field(default=1_000_000)
    AI_MONTHLY_COST_LIMIT_USD: float = Field(default=100.0)

    # AI Rate Limiting
    AI_COMPANY_RPM_LIMIT: int = Field(default=60)  # requests per minute per company
    AI_USER_DAILY_LIMIT: int = Field(default=50)   # requests per day per user

    # Stripe - Optional; when absent billing operates in tracking-only mode
    STRIPE_SECRET_KEY: str = Field(default="")
    STRIPE_PUBLISHABLE_KEY: str = Field(default="")
    STRIPE_WEBHOOK_SECRET: str = Field(default="")

    @property
    def STRIPE_ENABLED(self) -> bool:
        """Return True when Stripe is configured and available."""
        return bool(self.STRIPE_SECRET_KEY and self.STRIPE_SECRET_KEY.startswith("sk_"))

    # ------------------------------------------------------------------
    # S3 / R2 Object Storage - REQUIRED for production media storage
    # ------------------------------------------------------------------
    # Default storage provider: "local" | "s3" | "r2"
    STORAGE_PROVIDER: str = Field(default="local")
    S3_ENDPOINT_URL: str = Field(default="")
    S3_ACCESS_KEY_ID: str = Field(default="")
    S3_SECRET_ACCESS_KEY: str = Field(default="")
    S3_BUCKET_NAME: str = Field(default="ai-marketing-media")
    S3_REGION: str = Field(default="auto")
    # S3-compatible public URL (CDN / custom domain for public access)
    S3_PUBLIC_URL: str = Field(
        default="",
        description="Public URL prefix for S3 objects (CDN or custom domain). "
                    "If empty, falls back to CDN_URL or presigned URLs.",
    )

    R2_ENDPOINT_URL: str = Field(default="")
    R2_ACCESS_KEY_ID: str = Field(default="")
    R2_SECRET_ACCESS_KEY: str = Field(default="")
    R2_BUCKET_NAME: str = Field(default="ai-marketing-media")
    R2_REGION: str = Field(default="auto")
    # R2 Public URL (Cloudflare R2 custom domain / CDN)
    R2_PUBLIC_URL: str = Field(
        default="",
        description="Public URL prefix for R2 objects (e.g. https://pub-xxx.r2.dev). "
                    "If empty, falls back to CDN_URL or presigned URLs.",
    )

    # CDN / Public URL for media serving (e.g. Cloudflare R2 public URL)
    CDN_URL: str = Field(default="")

    # Local storage path (dev only - production must use S3/R2)
    MEDIA_STORAGE_PATH: str = Field(default="./media_storage")

    # Signed URL expiry (seconds)
    SIGNED_URL_EXPIRY_SECONDS: int = Field(default=3600)

    # Webhook verification token (must be set for production)
    WEBHOOK_VERIFY_TOKEN: str = Field(default="")

    @field_validator("STORAGE_PROVIDER")
    @classmethod
    def validate_storage_provider(cls, v: str) -> str:
        # 'disabled' = pilot staging: media upload kapalı
        allowed = {"local", "s3", "r2", "disabled"}
        if v.lower() not in allowed:
            raise ValueError(f"STORAGE_PROVIDER must be one of {allowed}, got: {v}")
        return v.lower()

    # Alias properties for compatibility with various env naming conventions
    @property
    def S3_ACCESS_KEY(self) -> str:
        return self.S3_ACCESS_KEY_ID

    @property
    def S3_SECRET_KEY(self) -> str:
        return self.S3_SECRET_ACCESS_KEY

    @property
    def R2_ACCESS_KEY(self) -> str:
        return self.R2_ACCESS_KEY_ID

    @property
    def R2_SECRET_KEY(self) -> str:
        return self.R2_SECRET_ACCESS_KEY

    @model_validator(mode="after")
    def validate_production_storage(self) -> "Settings":
        env = os.environ.get("ENVIRONMENT", "development").lower()
        if env in ("production", "staging") and self.STORAGE_PROVIDER == "local":
            raise ValueError(
                "STORAGE_PROVIDER cannot be 'local' in production/staging. "
                "Set STORAGE_PROVIDER=s3, STORAGE_PROVIDER=r2, or "
                "STORAGE_PROVIDER=disabled (media upload kapalı)."
            )
        # 'disabled' = pilot staging: media upload feature flag kapalı
        return self

    # ------------------------------------------------------------------
    # Secret validators (fail-fast on hardcoded / weak secrets)
    # ------------------------------------------------------------------

    DEFAULT_SECRET_VALUES: ClassVar[set] = {
        "your-secret-key",
        "your-secret-key-here",
        "changeme",
        "secret",
        "test",
        "super-secret-jwt-key-change-in-production",
        "super-secret-encryption-key-change-in-production",
        "super-secret-key-change-me",
        "default",
        "password",
        "123456",
        "admin",
        "jwt-secret",
        "jwt-secret-key",
        "jwt-secret-key-123",
        "encryption-key",
        "encryption-key-123",
        "my-secret",
        "my-secret-key",
        "placeholder",
        "sample",
        "demo",
        "dev",
        "development",
        "local",
        "localhost",
    }

    @staticmethod
    def _calculate_entropy(value: str) -> float:
        """Calculate Shannon entropy of a string.

        Higher entropy = more randomness = stronger secret.
        A truly random 32+ char secret should have entropy > 4.5 bits/char.
        """
        import math
        if not value:
            return 0.0
        freq = {}
        for ch in value:
            freq[ch] = freq.get(ch, 0) + 1
        length = len(value)
        entropy = 0.0
        for count in freq.values():
            p = count / length
            entropy -= p * math.log2(p)
        return entropy

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        # Fail-fast: secret must be provided
        if not v or len(v) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must be at least 32 characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        # Check against known weak/default values (case-insensitive)
        if v.lower() in cls.DEFAULT_SECRET_VALUES:
            raise ValueError(
                f"JWT_SECRET_KEY cannot be a default/placeholder value: '{v[:8]}...'. "
                f"Generate a secure secret with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        # Check entropy (reject low-entropy/repeated patterns)
        entropy = cls._calculate_entropy(v)
        if entropy < 3.5:
            raise ValueError(
                f"JWT_SECRET_KEY has too low entropy ({entropy:.2f} bits/char). "
                f"The secret appears to be predictable or repetitive. "
                f"Generate a cryptographically random secret: "
                f"python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        # Check for repeated character patterns
        if len(set(v)) < 8:
            raise ValueError(
                "JWT_SECRET_KEY must contain at least 8 unique characters. "
                "Generate a secure secret with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        # Check for hex pattern (secrets.token_hex output) - acceptable but flag if too short
        hex_chars = set("0123456789abcdefABCDEF")
        if all(c in hex_chars for c in v) and len(v) < 32:
            raise ValueError(
                "JWT_SECRET_KEY: hex-encoded secrets must be at least 32 characters "
                "(use secrets.token_hex(32) for a 64-char hex string)."
            )
        return v

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if not v or len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        # Check against known weak/default values
        if v.lower() in cls.DEFAULT_SECRET_VALUES:
            raise ValueError(
                f"SECRET_KEY cannot be a default/placeholder value: '{v[:8]}...'. "
                f"Generate a secure secret with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        # Check entropy
        entropy = cls._calculate_entropy(v)
        if entropy < 3.5:
            raise ValueError(
                f"SECRET_KEY has too low entropy ({entropy:.2f} bits/char). "
                f"The secret appears to be predictable or repetitive. "
                f"Generate a cryptographically random secret: "
                f"python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        # Check for repeated character patterns
        if len(set(v)) < 8:
            raise ValueError(
                "SECRET_KEY must contain at least 8 unique characters. "
                "Generate a secure secret with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v

    @model_validator(mode="after")
    def validate_keys_are_different(self) -> "Settings":
        """Ensure JWT_SECRET_KEY and SECRET_KEY are different values."""
        if self.JWT_SECRET_KEY == self.SECRET_KEY:
            raise ValueError(
                "JWT_SECRET_KEY and SECRET_KEY must be different values. "
                "Using the same key for signing tokens and encryption breaks security isolation. "
                "Generate two independent secrets: "
                "python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return self

    @model_validator(mode="after")
    def validate_mysql_password_not_hardcoded(self) -> "Settings":
        # When Railway provides individual MySQL env vars, ensure password is real
        if os.environ.get("MYSQLHOST") and not os.environ.get("MYSQLPASSWORD"):
            raise ValueError(
                "MYSQLPASSWORD is required when MYSQLHOST is set. "
                "Check Railway dashboard > MySQL service > Connect."
            )
        return self

    @model_validator(mode="after")
    def validate_jwt_source_environment(self) -> "Settings":
        """In production, ensure JWT_SECRET_KEY comes from environment, not code defaults."""
        env = os.environ.get("ENVIRONMENT", "development").lower()
        if env in ("production", "staging"):
            jwt_from_env = os.environ.get("JWT_SECRET_KEY")
            secret_from_env = os.environ.get("SECRET_KEY")
            if not jwt_from_env:
                raise ValueError(
                    "JWT_SECRET_KEY must be explicitly set via environment variable "
                    "in production/staging. It cannot rely on .env file defaults."
                )
            if not secret_from_env:
                raise ValueError(
                    "SECRET_KEY must be explicitly set via environment variable "
                    "in production/staging. It cannot rely on .env file defaults."
                )
        return self

    @model_validator(mode="after")
    def validate_openai_key_source(self) -> "Settings":
        """Flag if OpenAI key is present but looks like a placeholder."""
        if self.OPENAI_API_KEY:
            if self.OPENAI_API_KEY.lower() in {"", "placeholder", "your-key-here", "sk-test"}:
                # Non-fatal: just clear it so graceful fallback activates
                self.OPENAI_API_KEY = ""
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="",
        extra="ignore",
    )


settings = Settings()
