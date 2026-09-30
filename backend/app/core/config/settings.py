"""Application settings loaded from environment variables.

Uses pydantic-settings to validate and parse configuration from ``.env`` files
and environment variables.  Every setting has a sensible default so the
application can start in development without an ``.env`` file present, but
**production deployments must override all secrets and URLs**.
"""

from __future__ import annotations

import contextlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import (
    AliasChoices,
    AnyHttpUrl,
    Field,
    PostgresDsn,
    RedisDsn,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration sourced from environment."""

    # Absolute path, not a bare ".env": a relative path is resolved against the
    # process working directory, so starting uvicorn from the repo root instead
    # of backend/ silently loaded NO .env at all. The app then ran on defaults —
    # the placeholder JWT secret, and ENVIRONMENT=development, which skips the
    # production safety validator entirely — with no error to notice.
    _ENV_FILE = Path(__file__).resolve().parents[3] / ".env"

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────
    APP_NAME: str = "Iranian E-Commerce"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ─ API ───────────────────────────────────────────────────────────────
    API_V1_PREFIX: str = "/api/v1"
    # Interactive docs (/docs, /redoc, /openapi.json) are auto-disabled when
    # ENVIRONMENT=production. Set true only to serve them deliberately behind
    # an internal network or an nginx allowlist.
    ENABLE_API_DOCS: bool = False

    # Bearer token required to scrape /metrics when ENVIRONMENT=production.
    # The endpoint is reachable through nginx (/api/v1/metrics sits under the
    # proxied /api/ prefix) and its labels enumerate every route path,
    # including /admin/* — an unauthenticated scrape is a free API map. A
    # Prometheus collector can set `authorization: {credentials: <token>}`.
    # In development/staging the endpoint stays open so local scraping works
    # without setup.
    METRICS_TOKEN: str = ""

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

    # ── SSO / OIDC (Google) ───────────────────────────────────────────────
    # Empty client id/redirect URI means SSO login is disabled; the endpoints
    # answer SSO_NOT_CONFIGURED instead of failing mid-flow.
    GOOGLE_OAUTH_CLIENT_ID: str = ""
    GOOGLE_OAUTH_CLIENT_SECRET: str = ""
    GOOGLE_OAUTH_REDIRECT_URI: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Security Audit & Compliance Logging (FATA / Shaparak) ─────────────
    AUDIT_LOG_FILE: str = "logs/security_audit.log"
    AUDIT_LOG_ENABLED: bool = True
    AUDIT_LOG_HMAC_KEY: str = ""
    AUDIT_LOG_MAX_BYTES: int = 50 * 1024 * 1024  # 50 MB
    AUDIT_LOG_BACKUP_COUNT: int = 30

    # ── CORS ──────────────────────────────────────────────────────────────
    # Both env names are honoured: the deployment docs and the shipped
    # .env/.env.example files have historically used BACKEND_CORS_ORIGINS,
    # while the field is CORS_ORIGINS. Without the alias the documented
    # variable was silently ignored and production booted with the dev
    # default list — the exact configuration the deploy guide told operators
    # not to rely on. NoDecode keeps a comma-separated string intact so the
    # validator below can split it (pydantic would otherwise try to JSON-parse
    # a list field and raise an opaque SettingsError on the documented form).
    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(  # type: ignore[pydantic-alias]
        default=[
            "http://localhost:3000",
            "http://localhost",
            "https://site.arouxpingg.com",
            "http://site.arouxpingg.com",
            "http://91.107.144.136",
        ],
        validation_alias=AliasChoices("CORS_ORIGINS", "BACKEND_CORS_ORIGINS"),
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            raw = v.strip()
            if raw.startswith("["):
                # Accept a JSON array as well as the comma form.
                with contextlib.suppress(ValueError):
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return [str(o).strip() for o in parsed if str(o).strip()]
            return [origin.strip() for origin in raw.split(",") if origin.strip()]
        if isinstance(v, list):
            return v
        return [str(v)]

    # ── Sentry ────────────────────────────────────────────────────────────
    SENTRY_DSN: str | None = None
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    # ── OpenTelemetry & Observability ─────────────────────────────────────
    OTEL_ENABLED: bool = True
    OTEL_SERVICE_NAME: str = "iranian-ecommerce-backend"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4318"
    OTEL_TRACES_SAMPLER_RATIO: float = 1.0
    DATABASE_SLOW_QUERY_THRESHOLD_MS: float = 100.0
    REDIS_SLOW_OPERATION_THRESHOLD_MS: float = 20.0
    API_SLOW_REQUEST_THRESHOLD_MS: float = 700.0
    API_CRITICAL_REQUEST_THRESHOLD_MS: float = 1400.0
    OBSERVABILITY_DEBUG: bool = False

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

    # ── Email (SMTP) Provider ─────────────────────────────────────────────
    # Email delivery is DISABLED while SMTP_HOST is blank: the notification
    # service then keeps the previous mock behavior (log-only) and the
    # capability registry reports the channel as not configured. Port 465
    # implies implicit SSL, 587 STARTTLS, 25 plain (relays only).
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    # True = STARTTLS after connect; False + port 465 = implicit SSL.
    SMTP_USE_TLS: bool = True
    SMTP_FROM_ADDRESS: str = ""
    SMTP_FROM_NAME: str = "فروشگاه اینترنتی"
    SMTP_TIMEOUT_SECONDS: int = 15

    # ── Telegram Bot Provider ─────────────────────────────────────────────
    # Telegram delivery is DISABLED while TELEGRAM_BOT_TOKEN is blank: the
    # notification service then keeps the previous mock behavior (log-only)
    # and the capability registry reports the channel as not configured.
    # Per-user delivery targets live in notification_preferences.telegram_chat_id
    # (users link their account via the verification-code flow — see
    # telegram_service.py). The optional username only feeds the admin UI's
    # deep-link hint (https://t.me/<username>).
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_BOT_USERNAME: str = ""
    TELEGRAM_API_BASE_URL: str = "https://api.telegram.org"
    TELEGRAM_TIMEOUT_SECONDS: int = 15

    # ── Web Push (VAPID) Provider ─────────────────────────────────────────
    # Web push needs the `pywebpush` package, which is NOT installed (see
    # push_service.py for the documented dependency gap). VAPID keys are
    # configured here so the subscription endpoints work today and the
    # provider flips from "not configured" to live the moment the package
    # and keys are both present. Generate keys with:
    #   pywebpush gen-vapid (or `npx web-push generate-vapid-keys`)
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_SUBJECT: str = "mailto:support@site.com"
    PUSH_TIMEOUT_SECONDS: int = 15

    # ── Identity Verification (Karta Zohal: Shahkar / civil registry) ────
    # Without a real token the KYC endpoints report UNAVAILABLE — trust is
    # never granted from unverified input (P0.1).
    IDENTITY_PROVIDER_BASE_URL: str = "https://service.zohal.io/api/v0"
    IDENTITY_PROVIDER_TOKEN: str = ""
    IDENTITY_PROVIDER_TIMEOUT_SECONDS: int = 10

    # ── Storefront ────────────────────────────────────────────────────────
    # Canonical customer-facing origin. Used wherever the backend must hand a
    # customer a link back into the shop (cart-recovery reminders, e-mail
    # deep links). Must be the public origin in production, never localhost.
    STOREFRONT_BASE_URL: str = "http://localhost:3000"

    # ── Abandoned Cart Recovery ───────────────────────────────────────────
    # A cart with items that has seen no activity for this many minutes is
    # eligible for a recovery reminder. Stages are cumulative checkpoints:
    # the Nth entry is the follow-up sent that many minutes after the last
    # activity, and each cart receives at most one reminder per stage.
    CART_RECOVERY_STAGES_MINUTES: list[int] = [120, 1440]
    CART_RECOVERY_ENABLED: bool = True
    # Upper bound on reminders per task run, so a backlog can never turn one
    # run into an unbounded outbound-SMS burst.
    CART_RECOVERY_BATCH_SIZE: int = 200
    # Recovery links are bearer credentials for one cart; keep the window
    # tight enough that a link found in an old SMS is no longer usable.
    CART_RECOVERY_TOKEN_TTL_DAYS: int = 7

    # ── Payment ───────────────────────────────────────────────────────────
    PAYMENT_PROVIDER: Literal["zarinpal", "idpay", "mock", "crypto", "card_transfer"] = "mock"
    PAYMENT_MERCHANT_ID: str = ""
    PAYMENT_CALLBACK_BASE_URL: str = "http://localhost:3000/payment/callback"
    PAYMENT_SANDBOX: bool = True
    ORDER_PAYMENT_TIMEOUT_MINUTES: int = 60
    # Number of trusted reverse proxies in front of the app (nginx = 1).
    # Controls how many rightmost X-Forwarded-For hops are trusted.
    TRUSTED_PROXY_COUNT: int = 1
    # Where the browser-facing scheme is actually terminated. "proxy" means a
    # TLS-terminating nginx/load balancer in front of uvicorn (this stack's
    # documented production topology); "app" means uvicorn terminates TLS
    # itself. This is a DECLARATION of intent by the operator — the app has no
    # way to observe its own public-facing scheme, because a health check
    # running inside the app only ever sees the hop on the compose network,
    # which is plain HTTP by design. It is deliberately NOT auto-derived from
    # ENVIRONMENT: an undeclared production deployment must not read "good",
    # because that is precisely the silent-plaintext-HTTP failure the HTTPS
    # site-health check exists to catch. Unset/"auto" reports "undeterminable".
    TLS_TERMINATION: Literal["proxy", "app", "auto"] = "auto"
    # Minimum wallet top-up amount in IRR (TASK P6-02)
    WALLET_TOPUP_MIN_IRIALS: int = 100_000
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

    # ── Rate Limiting (slowapi, per-IP) ───────────────────────────────────
    # RATE_LIMIT_GLOBAL is the middleware-wide ceiling applied to EVERY route
    # via application_limits (default_limits=[] previously left every
    # undecorated route unlimited). The rest are per-route budgets used by
    # decorators. All env-overridable so ops can tighten without a deploy.
    RATE_LIMIT_GLOBAL: str = "200/minute"
    RATE_LIMIT_LOGIN: str = "5/minute"
    RATE_LIMIT_REGISTER: str = "5/minute"
    RATE_LIMIT_OTP_REQUEST: str = "3/minute"
    RATE_LIMIT_OTP_VERIFY: str = "10/minute"
    # Password reset mails are the enumeration-safe endpoint, so the limit is
    # per-IP rather than per-address: one attacker must not be able to walk a
    # list of addresses, and a shared office NAT must not lock out real users.
    RATE_LIMIT_PASSWORD_RESET_REQUEST: str = "3/minute"
    RATE_LIMIT_PASSWORD_RESET_CONFIRM: str = "10/minute"
    RATE_LIMIT_REFRESH: str = "30/minute"
    RATE_LIMIT_SEARCH: str = "30/minute"
    RATE_LIMIT_SEARCH_SUGGEST: str = "60/minute"

    # ── HTTP Cache (ETag / optional page cache) ──────────────────────────
    # ETag/304 negotiation for anonymous API GETs is always on (see
    # app/core/http_cache.py). The full-response page cache below is strictly
    # opt-in: it serves repeat anonymous GETs under PAGE_CACHE_PATH_PREFIXES
    # from Redis for PAGE_CACHE_TTL_SECONDS. Public, read-only prefixes only —
    # anything with credentials, Set-Cookie, or no-store is never cached.
    PAGE_CACHE_ENABLED: bool = False
    # Comma-separated list in the environment; leading slash required for a
    # match (boundary-aware: "/api/v1/blog" does not match "/api/v1/blog-admin").
    PAGE_CACHE_PATH_PREFIXES: Annotated[list[str], NoDecode] = Field(  # type: ignore[pydantic-alias]
        default=["/api/v1/settings/public", "/api/v1/blog", "/api/v1/content"],
    )
    PAGE_CACHE_TTL_SECONDS: int = 60

    @field_validator("PAGE_CACHE_PATH_PREFIXES", mode="before")
    @classmethod
    def assemble_page_cache_prefixes(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [p.strip() for p in v.split(",") if p.strip()]
        if isinstance(v, list):
            return v
        return [str(v)]

    # ── Celery ────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Misc ──────────────────────────────────────────────────────────────
    UPLOAD_DIR: str = "media"
    ALLOWED_UPLOAD_EXTENSIONS: list[str] = Field(
        default=[".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"]
    )
    MAX_UPLOAD_SIZE_MB: int = 10
    DIGITAL_CARDS_ENCRYPTION_KEY: str = Field(
        default="CHANGE-ME-use-base64-32bytes-key",
        description="Base64 encoded 32-byte key for AES-256-GCM encryption of digital card PINs",
    )
    # Rotation history (Karta key rotation): comma-separated previous base64
    # keys. Decryption accepts them so rotation is downtime-free; the admin
    # re-encrypt sweep then moves every payload onto the active key.
    DIGITAL_CARDS_PREVIOUS_KEYS: str = Field(
        default="",
        description="Comma-separated previous DIGITAL_CARDS_ENCRYPTION_KEY values for rotation",
    )
    ADMIN_PHONE: str = ""
    ADMIN_PASSWORD: str = ""

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
                raise ValueError(
                    "Security violation: JWT_SECRET_KEY contains placeholder in production"
                )
            if len(self.JWT_SECRET_KEY) < 24:
                raise ValueError(
                    "Security violation: JWT_SECRET_KEY must be at least 24 chars in production"
                )
            if "dev-only-secret-key" in self.JWT_SECRET_KEY.lower():
                raise ValueError(
                    "Security violation: JWT_SECRET_KEY must not be the known development "
                    "secret in production"
                )
            db_url = str(self.DATABASE_URL)
            # Match known DEFAULT credential pairs only — a legitimate strong
            # password may itself contain the word "password" (found via the
            # Phase 3 preflight: the old substring rule rejected e.g.
            # "...:EcomPassword@host").
            if "postgres:postgres@" in db_url or "postgres:password@" in db_url:
                raise ValueError(
                    "Security violation: DATABASE_URL contains default credentials in production"
                )
            if self.MINIO_SECRET_KEY in ("minioadmin", "minioadmin123"):
                raise ValueError(
                    "Security violation: MINIO_SECRET_KEY contains default credentials in production"  # noqa: E501
                )
            if self.MINIO_ACCESS_KEY == "minioadmin":
                raise ValueError(
                    "Security violation: MINIO_ACCESS_KEY contains default credentials in production"  # noqa: E501
                )
            if self.PAYMENT_PROVIDER == "mock":
                raise ValueError(
                    "Security violation: PAYMENT_PROVIDER cannot be 'mock' in production (PAY-001)"
                )
            if self.SMS_PROVIDER == "mock":
                raise ValueError(
                    "Security violation: SMS_PROVIDER cannot be 'mock' in production — "
                    "OTP login would grant account access to anyone (AUTH-001)"
                )
            if self.PAYMENT_SANDBOX:
                raise ValueError(
                    "Security violation: PAYMENT_SANDBOX must be False in production (PAY-001)"
                )
            cards_key = self.DIGITAL_CARDS_ENCRYPTION_KEY
            if not cards_key or cards_key.startswith("CHANGE-ME"):
                raise ValueError(
                    "Security violation: DIGITAL_CARDS_ENCRYPTION_KEY must be a real "
                    "base64 32-byte key in production (card PINs would be unreadable "
                    "or encrypted with a publicly known key)"
                )
            _weak_admin_passwords = {
                "admin", "admin123", "admin@123456", "password", "12345678",
                "admin@123", "changeme", "administrator",
            }
            if (
                not self.ADMIN_PASSWORD
                or len(self.ADMIN_PASSWORD) < 12
                or self.ADMIN_PASSWORD.lower() in _weak_admin_passwords
            ):
                raise ValueError(
                    "Security violation: ADMIN_PASSWORD must be a strong unique value "
                    "(min 12 chars) in production"
                )
            # Length alone is not enough: the .env.example placeholder is long
            # enough to pass it, and copying the example into .env is exactly
            # how a deployment ends up with a publicly known scrape token.
            metrics_token = self.METRICS_TOKEN
            token_is_placeholder = any(
                marker in metrics_token.lower()
                for marker in ("change_me", "changeme", "change-me", "your-", "placeholder")
            )
            if len(metrics_token) < 16 or token_is_placeholder:
                raise ValueError(
                    "Security violation: METRICS_TOKEN must be a real value of at "
                    "least 16 characters in production (generate with "
                    "`openssl rand -hex 32`) — /metrics is reachable through nginx "
                    "and its labels expose every route path"
                )
            insecure_cors = [
                o for o in self.CORS_ORIGINS if o.startswith("http://")
            ]
            if insecure_cors:
                raise ValueError(
                    "Security violation: CORS_ORIGINS contains plain-HTTP origins "
                    f"not allowed in production: {insecure_cors}"
                )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()
