"""P5-3 suggest: deterministic cards + constrained LLM priority pick.

Covers the worker ``execute_suggest`` ledger writes and the API surface:
deterministic ``GET /copilot/suggestions`` (always available), enqueue-only
``POST /copilot/suggest``, and the recommendation read.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api import db as db_module
from services.api.db import Base
from services.api.models import (
    Backtest,
    CopilotSuggestion,
    CopilotSuggestionStatus,
    Strategy,
    StrategyVersion,
)
from services.api.settings import get_settings
from services.worker.tasks.copilot import execute_suggest


def _code() -> str:
    return (
        "class A(QCAlgorithm):\n"
        "    def Initialize(self):\n"
        '        self.lookback = int(self.GetParameter("lookback"))\n'
        '        self.sp = self.GetParameter("slippage_bps")\n'
    )


def _seed_full(db, *, status: str = "BACKTESTED") -> tuple[Strategy, StrategyVersion]:
    """Strategy with one version + a completed backtest => runnable candidates."""
    strategy = Strategy(id=uuid4(), name="SPY 200DMA", status=status, benchmark="SPY")
    db.add(strategy)
    version = StrategyVersion(
        id=uuid4(),
        strategy_id=strategy.id,
        version=1,
        code=_code(),
        config={},
    )
    db.add(version)
    backtest = Backtest(
        id=uuid4(),
        strategy_version_id=version.id,
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
        status="COMPLETED",
        parameters={},
    )
    db.add(backtest)
    db.commit()
    return strategy, version


def _seed_strategy(db) -> Strategy:
    strategy = Strategy(id=uuid4(), name="SPY 200DMA", status="BACKTESTED", benchmark="SPY")
    db.add(strategy)
    db.commit()
    return strategy


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


def _fake_provider(*, exc: Exception | None = None, enabled: bool = True):
    calls: list[tuple[dict, list[dict]]] = []

    def suggest(context, candidates):
        calls.append((context, candidates))
        if exc is not None:
            raise exc
        return {"picked_id": candidates[0]["key"], "reason": "建议先做这条。"}

    return SimpleNamespace(name="deepseek", enabled=enabled, suggest=suggest), calls


def _suggestion_rows(Session) -> list[CopilotSuggestion]:
    with Session() as db:
        return list(db.execute(select(CopilotSuggestion)).scalars())


# ---------------------------------------------------------------- worker task


def test_execute_suggest_records_done_row(db_session, monkeypatch) -> None:
    provider, calls = _fake_provider()
    monkeypatch.setattr("services.worker.tasks.copilot.get_provider", lambda: provider)
    with db_session() as db:
        strategy, _version = _seed_full(db)
        strategy_id = strategy.id

    result = execute_suggest("strategy", str(strategy_id))

    assert result["status"] == "done"
    rows = _suggestion_rows(db_session)
    assert len(rows) == 1
    row = rows[0]
    assert row.status == CopilotSuggestionStatus.DONE
    assert row.picked_id == "run_validation:WALK_FORWARD"
    assert row.reason == "建议先做这条。"
    assert row.strategy_id == strategy_id
    assert row.model == "deepseek-v4-flash"
    assert calls[0][0]["total_trials"] == 0
    assert all("code" not in card for card in calls[0][1])


def test_execute_suggest_out_of_set_pick_records_failed(db_session, monkeypatch) -> None:
    provider = SimpleNamespace(
        name="deepseek",
        enabled=True,
        suggest=lambda context, candidates: {
            "picked_id": "run_validation:DSR",
            "reason": "越界",
        },
    )
    monkeypatch.setattr("services.worker.tasks.copilot.get_provider", lambda: provider)
    with db_session() as db:
        strategy, _version = _seed_full(db)
        strategy_id = strategy.id

    result = execute_suggest("strategy", str(strategy_id))

    assert result["status"] == "failed"
    rows = _suggestion_rows(db_session)
    assert len(rows) == 1
    assert rows[0].status == CopilotSuggestionStatus.FAILED
    assert "候选内" in (rows[0].error or "")


def test_execute_suggest_provider_error_records_failed(db_session, monkeypatch) -> None:
    from services.agent.copilot.providers import CopilotProviderError

    provider, _calls = _fake_provider(exc=CopilotProviderError("无法连接 DeepSeek"))
    monkeypatch.setattr("services.worker.tasks.copilot.get_provider", lambda: provider)
    with db_session() as db:
        strategy, _version = _seed_full(db)
        strategy_id = strategy.id

    result = execute_suggest("strategy", str(strategy_id))

    assert result["status"] == "failed"
    rows = _suggestion_rows(db_session)
    assert rows[0].status == CopilotSuggestionStatus.FAILED
    assert "无法连接" in (rows[0].error or "")


def test_execute_suggest_disabled_provider_records_failed(db_session) -> None:
    with db_session() as db:
        strategy, _version = _seed_full(db)
        strategy_id = strategy.id

    result = execute_suggest("strategy", str(strategy_id))

    assert result["status"] == "failed"
    rows = _suggestion_rows(db_session)
    assert rows[0].status == CopilotSuggestionStatus.FAILED
    assert "STREET_DEEPSEEK_API_KEY" in (rows[0].error or "")


def test_execute_suggest_no_candidates_records_failed(db_session, monkeypatch) -> None:
    provider, _calls = _fake_provider()
    monkeypatch.setattr("services.worker.tasks.copilot.get_provider", lambda: provider)
    with db_session() as db:
        strategy = _seed_strategy(db)  # no version, no backtest => no candidates
        strategy_id = strategy.id

    result = execute_suggest("strategy", str(strategy_id))

    assert result["status"] == "failed"
    rows = _suggestion_rows(db_session)
    assert rows[0].status == CopilotSuggestionStatus.FAILED
    assert "没有可建议的动作" in (rows[0].error or "")


def test_execute_suggest_missing_resource_no_row(db_session) -> None:
    result = execute_suggest("strategy", str(uuid4()))
    assert result == {"status": "not_found", "detail": "策略不存在"}
    assert _suggestion_rows(db_session) == []


# ------------------------------------------------------------------ API layer


def test_get_suggestions_lists_deterministic_cards(client) -> None:
    with db_module.SessionLocal() as db:
        strategy, _version = _seed_full(db)
        strategy_id = strategy.id

    response = client.get(f"/api/v1/copilot/suggestions?strategy_id={strategy_id}")

    assert response.status_code == 200
    candidates = response.json()["candidates"]
    kinds = {c["validation_kind"] for c in candidates if c["action"] == "run_validation"}
    assert {"WALK_FORWARD", "PBO", "SENSITIVITY", "COST"} <= kinds
    assert all(c["executable"] is True for c in candidates if c["action"] == "run_validation")
    assert "DSR" not in kinds
    # PBO carries an explicit grid so the confirm-execute payload is valid.
    pbo = next(c for c in candidates if c["validation_kind"] == "PBO")
    assert len(pbo["params"]["values"]) == 5


def test_get_suggestions_unknown_strategy_404(client) -> None:
    response = client.get(f"/api/v1/copilot/suggestions?strategy_id={uuid4()}")
    assert response.status_code == 404


def test_get_suggestions_guide_when_no_backtest(client) -> None:
    with db_module.SessionLocal() as db:
        strategy = _seed_strategy(db)
        version = StrategyVersion(
            id=uuid4(), strategy_id=strategy.id, version=1, code=_code(), config={}
        )
        db.add(version)
        db.commit()
        strategy_id = strategy.id

    response = client.get(f"/api/v1/copilot/suggestions?strategy_id={strategy_id}")

    assert response.status_code == 200
    cards = response.json()["candidates"]
    assert len(cards) == 1
    assert cards[0]["reason_code"] == "backtest_first"
    assert cards[0]["action"] == "guide"
    assert cards[0]["executable"] is False


def test_get_recommendation_empty_is_null(client) -> None:
    with db_module.SessionLocal() as db:
        strategy = _seed_strategy(db)
        strategy_id = strategy.id

    response = client.get(f"/api/v1/copilot/suggestions/recommendation?strategy_id={strategy_id}")

    assert response.status_code == 200
    assert response.json() is None


def test_get_recommendation_returns_newest_row(client) -> None:
    with db_module.SessionLocal() as db:
        strategy = _seed_strategy(db)
        strategy_id = strategy.id
        now = datetime.now(timezone.utc)
        db.add(
            CopilotSuggestion(
                id=uuid4(),
                strategy_id=strategy_id,
                status=CopilotSuggestionStatus.DONE,
                model="deepseek-v4-flash",
                picked_id="run_validation:PBO",
                reason="先补 PBO 闸门。",
                created_at=now,
                finished_at=now,
            )
        )
        db.commit()

    response = client.get(f"/api/v1/copilot/suggestions/recommendation?strategy_id={strategy_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["picked_id"] == "run_validation:PBO"
    assert payload["reason"] == "先补 PBO 闸门。"
    assert payload["status"] == "DONE"


def test_post_suggest_503_when_provider_disabled(client) -> None:
    with db_module.SessionLocal() as db:
        strategy = _seed_strategy(db)
        strategy_id = strategy.id
    response = client.post(
        "/api/v1/copilot/suggest", json={"resource": "strategy", "id": str(strategy_id)}
    )
    assert response.status_code == 503
    assert "未启用" in response.json()["detail"]


def test_post_suggest_enqueues_202(client, monkeypatch) -> None:
    captured: list[tuple[str, str]] = []

    class _FakeTask:
        def delay(self, resource: str, resource_id: str) -> None:
            captured.append((resource, resource_id))

    monkeypatch.setattr("services.worker.tasks.run_suggest_task", _FakeTask())
    get_settings.cache_clear()
    monkeypatch.setenv("STREET_DEEPSEEK_API_KEY", "sk-test")
    try:
        with db_module.SessionLocal() as db:
            strategy = _seed_strategy(db)
            strategy_id = strategy.id
        response = client.post(
            "/api/v1/copilot/suggest", json={"resource": "strategy", "id": str(strategy_id)}
        )
        assert response.status_code == 202
        assert response.json() == {"status": "queued"}
        assert captured == [("strategy", str(strategy_id))]
    finally:
        get_settings.cache_clear()


def test_post_suggest_404_and_422(client) -> None:
    missing = client.post(
        "/api/v1/copilot/suggest", json={"resource": "strategy", "id": str(uuid4())}
    )
    assert missing.status_code == 404

    invalid = client.post("/api/v1/copilot/suggest", json={"resource": "note", "id": str(uuid4())})
    assert invalid.status_code == 422
