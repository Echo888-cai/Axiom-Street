import os

os.environ["AXIOM_DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["AXIOM_SYNC_BACKTESTS"] = "0"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def client():
    from services.api import db as db_module
    from services.api.db import Base, get_db
    from services.api.main import app

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

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_strategy_crud_and_version(client):
    create = client.post(
        "/api/v1/strategies",
        json={
            "name": "SPY 200DMA",
            "description": "Trend",
        },
    )
    assert create.status_code == 201, create.text
    strategy = create.json()
    assert strategy["name"] == "SPY 200DMA"
    assert strategy["latest_version"]["version"] == 1
    assert "Spy200DmaAlgorithm" in strategy["latest_version"]["code"]

    listed = client.get("/api/v1/strategies")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    version = client.post(
        f"/api/v1/strategies/{strategy['id']}/versions",
        json={
            "code": strategy["latest_version"]["code"] + "\n# tweak\n",
            "commit_message": "tweak",
            "config": strategy["latest_version"]["config"],
        },
    )
    assert version.status_code == 201
    assert version.json()["version"] == 2
