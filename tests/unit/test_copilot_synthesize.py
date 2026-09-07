"""P5-2 synthesize: enqueue-only API + worker ledger persistence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api import db as db_module
from services.api.db import Base
from services.api.models import CopilotInsight, CopilotInsightStatus, Strategy
from services.agent.copilot.providers import CopilotProviderError
from services.api.settings import get_settings
from services.worker.tasks.copilot import execute_synthesize


def _seed_strategy(db) -> Strategy:
    strategy = Strategy(
        id=uuid4(),
        name="SPY 200DMA",
        status="BACKTESTED",
        benchmark="SPY",
        family_id=None,
    )
    db.add(strategy)
    db.commit()
    return strategy


# ---------------------------------------------------------------- worker task


@pytest.fixture()
def db_session(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(db_module, "SessionLocal", Session)
    monkeypatch.setattr("services.worker.tasks.SessionLocal", Session)
    return Session


def _fake_provider(*, text: str | None = None, exc: Exception | None = None):
    calls: list[dict] = []

    def synthesize(context):
        calls.append(context)
        if exc is not None:
            raise exc
        return text

    return SimpleNamespace(name="deepseek", enabled=True, synthesize=synthesize), calls


def _insight_rows(Session) -> list[CopilotInsight]:
    with Session() as db:
        return list(db.execute(select(CopilotInsight)).scalars())


def test_execute_synthesize_records_done_row(db_session, monkeypatch) -> None:
    provider, calls = _fake_provider(text="别再在这份快照上试了,47 次都没过闸门。")
    monkeypatch.setattr("services.worker.tasks.copilot.get_provider", lambda: provider)
    with db_session() as db:
        strategy = _seed_strategy(db)
        strategy_id = strategy.id

    result = execute_synthesize("strategy", str(strategy_id))

    assert result["status"] == "done"
    rows = _insight_rows(db_session)
    assert len(rows) == 1
    row = rows[0]
    assert row.strategy_id == strategy_id
    assert row.status == CopilotInsightStatus.DONE
    assert row.narrative == "别再在这份快照上试了,47 次都没过闸门。"
    assert row.model == "deepseek-v4-flash"
    assert row.duration_ms is not None
    assert calls[0]["total_trials"] == 0  # aggregate context dict was passed
    assert "code" not in calls[0]


def test_execute_synthesize_provider_error_records_failed_row(db_session, monkeypatch) -> None:
    provider, _calls = _fake_provider(exc=CopilotProviderError("DeepSeek API key 无效(401)"))
    monkeypatch.setattr("services.worker.tasks.copilot.get_provider", lambda: provider)
    with db_session() as db:
        strategy = _seed_strategy(db)
        strategy_id = strategy.id

    result = execute_synthesize("strategy", str(strategy_id))

    assert result["status"] == "failed"
    rows = _insight_rows(db_session)
    assert len(rows) == 1
    assert rows[0].status == CopilotInsightStatus.FAILED
    assert "401" in (rows[0].error or "")


def test_execute_synthesize_disabled_provider_records_failed_row(db_session) -> None:
    with db_session() as db:
        strategy = _seed_strategy(db)
        strategy_id = strategy.id

    result = execute_synthesize("strategy", str(strategy_id))

    assert result["status"] == "failed"
    rows = _insight_rows(db_session)
    assert len(rows) == 1
    assert rows[0].status == CopilotInsightStatus.FAILED
    assert "STREET_DEEPSEEK_API_KEY" in (rows[0].error or "")


def test_execute_synthesize_missing_resource_no_row(db_session) -> None:
    result = execute_synthesize("strategy", str(uuid4()))
    assert result == {"status": "not_found", "detail": "策略不存在"}
    assert _insight_rows(db_session) == []


# ------------------------------------------------------------------ API layer


def test_post_synthesize_503_when_provider_disabled(client) -> None:
    with db_module.SessionLocal() as db:
        strategy = _seed_strategy(db)
        strategy_id = strategy.id
    response = client.post(
        "/api/v1/copilot/synthesize",
        json={"resource": "strategy", "id": str(strategy_id)},
    )
    assert response.status_code == 503
    assert "未启用" in response.json()["detail"]
    assert "deepseek" in response.json()["detail"]


def test_post_synthesize_enqueues_202(client, monkeypatch) -> None:
    captured: list[tuple[str, str]] = []

    class _FakeTask:
        def delay(self, resource: str, resource_id: str) -> None:
            captured.append((resource, resource_id))

    monkeypatch.setattr("services.worker.tasks.run_synthesize_task", _FakeTask())
    get_settings.cache_clear()
    monkeypatch.setenv("STREET_DEEPSEEK_API_KEY", "sk-test")
    try:
        with db_module.SessionLocal() as db:
            strategy = _seed_strategy(db)
            strategy_id = strategy.id
        response = client.post(
            "/api/v1/copilot/synthesize",
            json={"resource": "strategy", "id": str(strategy_id)},
        )
        assert response.status_code == 202
        assert response.json() == {"status": "queued"}
        assert captured == [("strategy", str(strategy_id))]
    finally:
        get_settings.cache_clear()


def test_post_synthesize_404_and_422(client, monkeypatch) -> None:
    missing = client.post(
        "/api/v1/copilot/synthesize",
        json={"resource": "strategy", "id": str(uuid4())},
    )
    assert missing.status_code == 404

    invalid = client.post(
        "/api/v1/copilot/synthesize",
        json={"resource": "note", "id": str(uuid4())},
    )
    assert invalid.status_code == 422


def test_get_insights_lists_newest_first(client) -> None:
    with db_module.SessionLocal() as db:
        strategy = _seed_strategy(db)
        strategy_id = strategy.id
        now = datetime.now(timezone.utc)
        older = CopilotInsight(
            id=uuid4(),
            strategy_id=strategy_id,
            status=CopilotInsightStatus.FAILED,
            model="deepseek-v4-flash",
            narrative="",
            error="余额不足",
            duration_ms=5,
            created_at=now - timedelta(minutes=1),
            finished_at=now - timedelta(minutes=1),
        )
        newer = CopilotInsight(
            id=uuid4(),
            strategy_id=strategy_id,
            status=CopilotInsightStatus.DONE,
            model="deepseek-v4-flash",
            narrative="目前看不出必须停的理由。",
            duration_ms=812,
            created_at=now,
            finished_at=now,
        )
        db.add_all([older, newer])
        db.commit()
        newer_id = newer.id

    response = client.get(f"/api/v1/copilot/insights?strategy_id={strategy_id}")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert payload[0]["id"] == str(newer_id)
    assert payload[0]["status"] == "DONE"
    assert payload[0]["narrative"] == "目前看不出必须停的理由。"
    assert payload[1]["status"] == "FAILED"
    assert payload[1]["error"] == "余额不足"


def test_get_insights_unknown_strategy_is_empty(client) -> None:
    response = client.get(f"/api/v1/copilot/insights?strategy_id={uuid4()}")
    assert response.status_code == 200
    assert response.json() == []
