from __future__ import annotations

import os

os.environ.setdefault("STREET_DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("STREET_SYNC_BACKTESTS", "1")
os.environ.setdefault("STREET_SKIP_MIGRATIONS", "1")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def client(monkeypatch):
    from services.api import db as db_module
    from services.api.db import Base, get_db
    from services.api.main import app
    from services.api.settings import get_settings

    get_settings.cache_clear()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db_module.engine = engine
    db_module.SessionLocal = TestingSessionLocal
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(
        "services.worker.tasks.execute_backtest",
        lambda _id: {"status": "QUEUED", "mocked": True},
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    get_settings.cache_clear()
