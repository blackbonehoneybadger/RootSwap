from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

FORBIDDEN_SECRETS = frozenset(
    {
        "changeme",
        "secret",
        "dev-secret",
        "test-secret",
        "your-secret-here",
        "jwt-secret",
        "rootswap-dev-jwt-secret-change-in-production",
    }
)


class AdminRoleEntry:
    def __init__(self, role: str, key: str) -> None:
        self.role = role
        self.key = key


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://rootswap:rootswap@localhost:5432/rootswap"
    redis_url: str = "redis://localhost:6379/0"
    redis_password: str | None = None

    jwt_secret: str = "rootswap-dev-jwt-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    encryption_key: str = "dev-encryption-key-32bytes-long!!"
    telegram_bot_token: str = "0000000000:DEV_TELEGRAM_BOT_TOKEN_PLACEHOLDER"
    telegram_webhook_secret: str = "dev-webhook-secret"

    cors_origins: str = "*"
    rate_limit_per_minute: int = 60

    quote_ttl_seconds: int = 300
    payment_instructions_ttl_seconds: int = 900
    polling_interval_seconds: int = 30

    service_fee_rate: float = 0.015
    referral_reward_rate: float = 0.25
    referral_reward_basis: Literal["service_fee", "net_margin"] = "service_fee"

    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_cooldown_seconds: int = 300

    partner_quote_timeout_seconds: float = 5.0

    admin_api_keys: str = "admin:dev-admin-key"

    emergency_stop: bool = False

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith("postgresql"):
            raise ValueError("database_url must be a PostgreSQL URL")
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def admin_keys_map(self) -> dict[str, AdminRoleEntry]:
        result: dict[str, AdminRoleEntry] = {}
        for entry in self.admin_api_keys.split(","):
            entry = entry.strip()
            if not entry:
                continue
            if ":" in entry:
                role_str, key = entry.split(":", 1)
                result[key.strip()] = AdminRoleEntry(role=role_str.strip().upper(), key=key.strip())
            else:
                result[entry] = AdminRoleEntry(role="ADMIN", key=entry)
        return result

    def validate_production(self) -> None:
        if self.environment != "production":
            return
        errors: list[str] = []
        if not self.jwt_secret or self.jwt_secret.lower() in FORBIDDEN_SECRETS:
            errors.append("JWT_SECRET is weak or default")
        if len(self.jwt_secret) < 32:
            errors.append("JWT_SECRET must be at least 32 characters in production")
        if not self.encryption_key or self.encryption_key.lower() in FORBIDDEN_SECRETS:
            errors.append("ENCRYPTION_KEY is missing or default")
        if len(self.encryption_key.encode()) < 32:
            errors.append("ENCRYPTION_KEY must be at least 32 bytes in production")
        if not self.redis_password:
            errors.append("REDIS password is required in production")
        if not self.telegram_webhook_secret or self.telegram_webhook_secret.lower() in FORBIDDEN_SECRETS:
            errors.append("Webhook secret is missing or default")
        if errors:
            raise RuntimeError("Production startup blocked: " + "; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production()
    return settings
