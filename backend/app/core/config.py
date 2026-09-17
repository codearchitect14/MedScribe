from functools import lru_cache

import email_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Disable DNS-based deliverability checks for email validation (EmailStr).
# This is a self-hosted reference system with no live transactional email
# provider wired up yet; requiring working DNS resolution for basic input
# validation is both unnecessary and unreliable in sandboxed/offline
# environments. Syntax validation still applies.
email_validator.CHECK_DELIVERABILITY = False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    database_url: str = "postgresql+asyncpg://medscribe:medscribe@localhost:5432/medscribe"
    sync_database_url: str = "postgresql+psycopg2://medscribe:medscribe@localhost:5432/medscribe"

    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    csrf_secret: str = "change-me-too"
    field_encryption_key: str = ""

    frontend_origin: str = "http://localhost:5173"

    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 900

    password_reset_token_expire_minutes: int = 30

    groq_api_key: str | None = None
    gemini_api_key: str | None = None

    groq_model: str = "openai/gpt-oss-20b"
    gemini_model: str = "gemini-2.5-flash"

    groq_base_url: str = "https://api.groq.com/openai/v1"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    # Which provider is tried first, and which one failover/load-balancing falls back to.
    llm_primary_provider: str = "groq"
    llm_secondary_provider: str = "gemini"
    # "primary_first" always tries llm_primary_provider first, failing over to the
    # secondary on error/exhausted quota. "round_robin" alternates between the two
    # when both currently have quota, for even load balancing across free tiers.
    llm_load_balance_strategy: str = "primary_first"

    # Conservative free-tier request budgets, tracked locally in Redis so the
    # gateway can switch provider before hitting a real 429. Adjust to match
    # your actual Groq/Gemini free-tier limits.
    groq_requests_per_minute: int = 25
    groq_requests_per_day: int = 800
    gemini_requests_per_minute: int = 12
    gemini_requests_per_day: int = 1000

    llm_request_timeout_seconds: float = 30.0
    llm_cache_ttl_seconds: int = 86400

    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384


@lru_cache
def get_settings() -> Settings:
    return Settings()
