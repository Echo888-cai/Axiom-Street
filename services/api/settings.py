from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STREET_", env_file=".env", extra="ignore")

    # Database credentials are intentionally NOT defaulted: the weak street:street
    # fallback was removed (EB-P5). Local dev supplies STREET_DATABASE_URL via .env.
    database_url: str = Field(min_length=1)
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    data_root: str = "data"
    jobs_root: str = "jobs"
    lean_image: str = "quantconnect/lean:16355"
    cors_origins: str = "http://localhost:3000"
    app_name: str = "Axiom Street"
    app_version: str = "0.1.0"
    risk_free_rate: float = 0.0
    lean_timeout_seconds: int = 1800
    sync_backtests: bool = False
    sync_ingests: bool = False
    max_inflight_backtests: int = 2
    worker_concurrency: int = 2
    lean_pool_size: int = 2
    lean_pool_warm: bool = False
    scan_parallelism: int = 2
    # Periodic full market re-pull to detect vendor restatements (seconds).
    market_reconcile_enabled: bool = True
    market_reconcile_interval_seconds: int = 86_400
    market_reconcile_provider: str = "auto"
    market_reconcile_with: str | None = None  # optional secondary, e.g. yfinance
    ingest_max_symbols: int = 500
    ingest_rps: float = 2.0
    ingest_concurrency: int = 4
    ingest_burst: float = 2.0

    # Observability (EB-P5). All SDK init is gated on these so unit tests never
    # dial out; compose enables them in the deployed stack.
    otel_enabled: bool = False
    otel_endpoint: str = "http://localhost:4317"  # OTLP/gRPC — Jaeger in compose
    prometheus_enabled: bool = True
    sentry_dsn: str = ""  # empty => Sentry fully no-op
    # AI copilot provider seam (P5-1). Only "noop" is registered until P5-2
    # wires Anthropic; an unknown name fails loud at request time.
    copilot_provider: str = "noop"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from env/.env, not kwargs
