from __future__ import annotations

import os
from contextlib import asynccontextmanager

import structlog
from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from services import telemetry
from services.api.db import Base, SessionLocal, engine
from services.api.health import collect_health
from services.api.models import User
from services.api.observability import RequestIdMiddleware, configure_logging
from services.api.routers import (
    audit,
    backtests,
    copilot,
    data,
    research,
    strategies,
    universes,
    validation,
    versions,
)
from services.api.routers import code as code_router
from services.api.schemas import HealthOut
from services.api.settings import get_settings


def _alembic_upgrade() -> None:
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")


def bootstrap_schema() -> None:
    """Apply schema via Alembic. In-memory/test DBs use create_all (no migration history)."""
    settings = get_settings()
    skip = os.getenv("STREET_SKIP_MIGRATIONS", "").lower() in {"1", "true", "yes"}
    if skip or ":memory:" in settings.database_url:
        Base.metadata.create_all(bind=engine)
        return
    _alembic_upgrade()


def seed_local_user() -> None:
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == "local@axiom.street").first()
        if not existing:
            db.add(User(email="local@axiom.street", display_name="David"))
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    bootstrap_schema()
    seed_local_user()
    yield


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,  # single-user, same-origin proxy — no cross-origin credentials (EB-P5)
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
# Outermost so it times the full request including CORS handling (EB-P5).
app.add_middleware(telemetry.PrometheusMiddleware)
telemetry.register_metrics(app)

app.include_router(strategies.router, prefix="/api/v1")
app.include_router(backtests.router, prefix="/api/v1")
app.include_router(versions.router, prefix="/api/v1")
app.include_router(data.router, prefix="/api/v1")
app.include_router(universes.router, prefix="/api/v1")
app.include_router(validation.router, prefix="/api/v1")
app.include_router(research.router, prefix="/api/v1")
app.include_router(code_router.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(copilot.router, prefix="/api/v1")

# OTel is the single tracer (OTLP -> Jaeger in the compose stack); Sentry is
# errors-only. Both are internal no-ops unless enabled in settings, so unit
# tests never dial out.
telemetry.configure_otel("axiom-api", app=app)
telemetry.configure_sentry()


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "code": "validation_error",
                "message": "请求校验失败",
                "errors": exc.errors(),
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    structlog.get_logger("api.unhandled").error(
        "unhandled exception", exc_type=type(exc).__name__, error=str(exc)
    )
    telemetry.capture_exception(exc)
    return JSONResponse(
        status_code=500,
        content={"detail": {"code": "internal_error", "message": str(exc)}},
    )


@app.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut.model_validate(collect_health())


@app.get("/api/v1/health", response_model=HealthOut)
def api_health() -> HealthOut:
    return health()
