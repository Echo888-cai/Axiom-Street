from __future__ import annotations

import os
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.db import Base, SessionLocal, engine
from services.api.models import User
from services.api.routers import backtests, data, strategies, versions
from services.api.schemas import HealthOut
from services.api.settings import get_settings


def _alembic_upgrade() -> None:
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")


def bootstrap_schema() -> None:
    """Apply schema via Alembic. In-memory/test DBs use create_all (no migration history)."""
    settings = get_settings()
    skip = os.getenv("AXIOM_SKIP_MIGRATIONS", "").lower() in {"1", "true", "yes"}
    if skip or ":memory:" in settings.database_url:
        Base.metadata.create_all(bind=engine)
        return
    _alembic_upgrade()


def seed_local_user() -> None:
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == "local@axiom.quant").first()
        if not existing:
            db.add(User(email="local@axiom.quant", display_name="David"))
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    bootstrap_schema()
    seed_local_user()
    yield


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(strategies.router, prefix="/api/v1")
app.include_router(backtests.router, prefix="/api/v1")
app.include_router(versions.router, prefix="/api/v1")
app.include_router(data.router, prefix="/api/v1")


@app.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok", service="api", version=settings.app_version)


@app.get("/api/v1/health", response_model=HealthOut)
def api_health() -> HealthOut:
    return health()
