"""Application settings loaded from environment variables.

Uses pydantic-settings to validate and parse configuration from ``.env`` files
and environment variables.  Every setting has a sensible default so the
application can start in development without an ``.env`` file present, but
**production deployments must override all secrets and URLs**.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, PostgresDsn, RedisDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


class Settings(BaseSettings):
    """Central configuration sourced from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────
    APP_NAME: str = "Iranian E-Commerce"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ── API ───────────────────────────────────────────────────────────────
    API_V1_PREFIX: str = "/api/v1"

    # ── Database ──────────────────────────────────────────────────────────
    DATABASE_URL: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/ecommerce"
    )
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False

    # ── Redis ─────────────────────────────────────────────────────────────
    REDIS_URL: RedisDsn = RedisDsn("redis://localhost:6379/0")
    REDIS_KEY_PREFIX: str = "ecom:"
    REDIS_DEFAULT_TTL: int = 300  # seconds

    # ── Elasticsearch ─────────────────────────────────────────────────────
    ELASTICSEARCH_URL: AnyHttpUrl = AnyHttpUrl("http://localhost:9200")
    ELASTICSEARCH_INDEX_PREFIX: str = "ecom_"

    # ── JWT / Auth ────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION-use-openssl-rand-hex-64"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── CORS ──────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost",
        "https://site.arouxpingg.com",
        "http://site.arouxpingg.com",
        "http://91.107.144.136",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [origin.strip() for origin in v.split(",")]
        if isinstance(v, list):
            return v
        return [v]  # type: ignore[list-item]

    # ── Sentry ────────────────────────────────────────────────────────────
    SENTRY_DSN: str | None = None
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    # ── MinIO / S3 ────────────────────────────────────────────────────────
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "ecommerce"
    MINIO_USE_SSL: bool = False
    MINIO_REGION: str = "us-east-1"

    # ── SMS Provider ──────────────────────────────────────────────────────
    SMS_PROVIDER: Literal["kavenegar", "ghasedak", "mock"] = "mock"
    SMS_API_KEY: str = ""
    SMS_SENDER_NUMBER: str = ""

    # ── Payment ───────────────────────────────────────────────────────────
    PAYMENT_PROVIDER: Literal["zarinpal", "idpay", "mock", "crypto", "card_transfer"] = "mock"
    PAYMENT_MERCHANT_ID: str = ""
    PAYMENT_CALLBACK_BASE_URL: str = "http://localhost:3000/payment/callback"
    PAYMENT_SANDBOX: bool = True
    ORDER_PAYMENT_TIMEOUT_MINUTES: int = 60
    NOWPAYMENTS_API_KEY: str = ""
    NOWPAYMENTS_SANDBOX: bool = True
    NOWPAYMENTS_IPN_SECRET: str = ""
    NOWPAYMENTS_IRR_PER_USD: int = 600_000
    CARD_TO_CARD_NUMBER: str = "6219-8610-1234-5678"
    CARD_TO_CARD_HOLDER: str = "فروشگاه آنلاین"
    CARD_TO_CARD_BANK: str = "بانک سامان"
    CARD_TO_CARD_INSTRUCTIONS: str = (
        "لطفاً مبلغ را به شماره کارت زیر واریز نموده و سپس شماره پیگیری / شماره ارجاع "
        "را در بخش ثبت فیش ارسال فرمایید. پس از بررسی و تأیید مدیریت، سفارش شما "
        "تکمیل خواهد شد."
    )

    # ── OTP ───────────────────────────────────────────────────────────────
    OTP_LENGTH: int = 6
    OTP_EXPIRY_SECONDS: int = 120
    OTP_MAX_ATTEMPTS: int = 5
    OTP_COOLDOWN_SECONDS: int = 60

    # ── Celery ────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Misc ──────────────────────────────────────────────────────────────
    UPLOAD_DIR: str = "media"
    ALLOWED_UPLOAD_EXTENSIONS: list[str] = Field(
        default=[".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"]
    )
    MAX_UPLOAD_SIZE_MB: int = 10

    @property
    def database_url_str(self) -> str:
        return str(self.DATABASE_URL)

    @property
    def redis_url_str(self) -> str:
        return str(self.REDIS_URL)

    @model_validator(mode="after")
    def validate_production_security(self) -> Self:
        """Fail fast in production if dangerous placeholders or debug flags are active."""
        if self.ENVIRONMENT == "production":
            if self.DEBUG:
                raise ValueError("Security violation: DEBUG must be False in production")
            if "CHANGE-ME" in self.JWT_SECRET_KEY or "changeme" in self.JWT_SECRET_KEY.lower():
                raise ValueError("Security violation: JWT_SECRET_KEY contains placeholder in production")
            if len(self.JWT_SECRET_KEY) < 24:
                raise ValueError("Security violation: JWT_SECRET_KEY must be at least 24 chars in production")
            db_url = str(self.DATABASE_URL)
            if "postgres:postgres@" in db_url or "password@" in db_url:
                raise ValueError("Security violation: DATABASE_URL contains default credentials in production")
            if self.MINIO_SECRET_KEY in ("minioadmin", "minioadmin123"):
                raise ValueError("Security violation: MINIO_SECRET_KEY contains default credentials in production")
            if self.PAYMENT_PROVIDER == "mock":
                raise ValueError("Security violation: PAYMENT_PROVIDER cannot be 'mock' in production (PAY-001)")
            if self.PAYMENT_SANDBOX:
                raise ValueError("Security violation: PAYMENT_SANDBOX must be False in production (PAY-001)")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()
