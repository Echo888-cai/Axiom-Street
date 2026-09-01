from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AXIOM_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://axiom:axiom@localhost:5432/axiom"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    data_root: str = "data"
    jobs_root: str = "jobs"
    lean_image: str = "quantconnect/lean:16355"
    cors_origins: str = "http://localhost:3000"
    app_name: str = "Axiom Quant"
    app_version: str = "0.1.0"
    risk_free_rate: float = 0.0
    lean_timeout_seconds: int = 1800

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
