"""Application settings.

Production safety: `validate_for_production()` is called on startup and hard-fails
when secrets are missing/weak or mock/sandbox partners are allowed as real sources.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

FORBIDDEN_SECRETS = {
    "",
    "secret",
    "changeme",
    "change-me",
    "default",
    "password",
    "test",
    "dev-secret",
    "insecure-dev-secret",
}

MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Environment: development | staging | production | test
    environment: str = "development"
    debug: bool = False

    app_name: str = "RootSwap"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://rootswap:rootswap@localhost:5432/rootswap"
    redis_url: str = "redis://localhost:6379/0"
    redis_password: str = ""

    jwt_secret: str = "insecure-dev-secret"
    jwt_algorithm: str = "HS256"
    jwt_ttl_seconds: int = 24 * 3600

    # Fernet key (urlsafe base64, 32 bytes). Required in production.
    encryption_key: str = ""

    telegram_bot_token: str = ""
    telegram_auth_max_age_seconds: int = 3600
    # In dev/test only: allow initData without signature check (never in production).
    telegram_auth_insecure_skip: bool = False

    # Shared secret for mock/sandbox partner webhooks.
    partner_webhook_secret: str = ""
    webhook_timestamp_tolerance_seconds: int = 300
    webhook_max_processing_attempts: int = 5

    # Fees / referral
    service_fee_percent: str = "0.9"  # % of amount_in
    referral_reward_basis: str = "service_fee"  # service_fee | net_margin
    referral_reward_percent: str = "20"  # % of the basis

    quote_ttl_seconds: int = 120
    payment_instructions_ttl_seconds: int = 900
    quote_partner_timeout_seconds: float = 3.0

    # Circuit breaker
    circuit_breaker_failure_threshold: int = 3
    circuit_breaker_cooldown_seconds: int = 60

    # Polling fallback
    polling_interval_seconds: int = 15
    polling_enabled: bool = False  # enabled in compose, off by default for tests

    # Rate limiting (requests per window per subject)
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 30
    rate_limit_window_seconds: int = 60

    # Partner environment gates
    allow_mock_partners: bool = True
    allow_sandbox_partners: bool = True

    # Admin RBAC: JSON mapping of telegram_id -> role, e.g. '{"12345": "ADMIN"}'
    admin_telegram_ids: str = "{}"

    cors_origins: str = "http://localhost:5173"

    notifications_enabled: bool = False

    log_level: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def validate_for_production(self) -> list[str]:
        """Return a list of blocking problems. Empty list == safe to start."""
        problems: list[str] = []
        if not self.is_production:
            return problems

        def weak(value: str) -> bool:
            return value.lower() in FORBIDDEN_SECRETS or len(value) < MIN_SECRET_LENGTH

        if weak(self.jwt_secret):
            problems.append("JWT_SECRET is missing, default or too weak (min 32 chars)")
        if not self.encryption_key:
            problems.append("ENCRYPTION_KEY is required in production")
        if not self.redis_password:
            problems.append("REDIS_PASSWORD is required in production")
        if not self.partner_webhook_secret or weak(self.partner_webhook_secret):
            problems.append("PARTNER_WEBHOOK_SECRET is missing or too weak")
        if not self.telegram_bot_token:
            problems.append("TELEGRAM_BOT_TOKEN is required in production")
        if self.telegram_auth_insecure_skip:
            problems.append("TELEGRAM_AUTH_INSECURE_SKIP must be disabled in production")
        if self.allow_mock_partners:
            problems.append("ALLOW_MOCK_PARTNERS must be false in production")
        if self.allow_sandbox_partners:
            problems.append("ALLOW_SANDBOX_PARTNERS must be false in production")
        if self.debug:
            problems.append("DEBUG must be disabled in production")
        return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()
