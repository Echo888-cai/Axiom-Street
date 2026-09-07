"""Copilot read-only context assembly (P5-1)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api import db as db_module
from services.api.db import Base
from services.api.models import (
    Backtest,
    DataSnapshot,
    ExperimentTrial,
    Strategy,
    StrategyVersion,
    ValidationRun,
)
from services.agent.copilot.context import build_context


def _ts(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with TestingSessionLocal() as session:
        yield session
    engine.dispose()


def _seed_strategy(db_session, *, name: str = "SPY 200DMA", family_id: UUID | None = None):
    strategy = Strategy(
        id=uuid4(),
        name=name,
        status="BACKTESTED",
        benchmark="SPY",
        family_id=family_id,
    )
    db_session.add(strategy)
    return strategy


def _seed_version(db_session, strategy: Strategy, version: int = 1) -> StrategyVersion:
    row = StrategyVersion(
        id=uuid4(),
        strategy_id=strategy.id,
        version=version,
        code="pass",
        config={},
        commit_message="v1",
    )
    db_session.add(row)
    return row


def _seed_snapshot(
    db_session,
    key: str,
    *,
    superseded_by: DataSnapshot | None = None,
) -> DataSnapshot:
    row = DataSnapshot(
        id=uuid4(),
        snapshot_key=key,
        provider="polygon",
        content_sha256="0" * 64,
        superseded_by=superseded_by.id if superseded_by else None,
    )
    db_session.add(row)
    return row


def _seed_trial(
    db_session,
    strategy: Strategy,
    snapshot: DataSnapshot | None,
    parameter_hash: str,
) -> ExperimentTrial:
    row = ExperimentTrial(
        id=uuid4(),
        strategy_id=strategy.id,
        strategy_family=strategy.family_id or strategy.id,
        data_snapshot_id=snapshot.id if snapshot else None,
        universe_key="SPY",
        parameter_hash=parameter_hash,
        is_oos=False,
    )
    db_session.add(row)
    return row


def _seed_validation_run(
    db_session,
    strategy: Strategy,
    *,
    kind: str,
    created_at: datetime,
    passed: bool = True,
    status: str = "COMPLETED",
) -> ValidationRun:
    row = ValidationRun(
        id=uuid4(),
        strategy_id=strategy.id,
        kind=kind,
        status=status,
        passed=passed,
        created_at=created_at,
        finished_at=created_at,
    )
    db_session.add(row)
    return row


def _seed_strategy_with_history(db_session) -> tuple[Strategy, dict[str, DataSnapshot]]:
    strategy = _seed_strategy(db_session)
    _seed_version(db_session, strategy)
    snap_new = _seed_snapshot(db_session, "spy-daily-20260901-1209a3")
    snap_old = _seed_snapshot(db_session, "spy-daily-20260831-1209a3", superseded_by=snap_new)
    # 3 trials on the superseded snapshot: hash h1 twice => 1 duplicate.
    _seed_trial(db_session, strategy, snap_old, "h1")
    _seed_trial(db_session, strategy, snap_old, "h2")
    _seed_trial(db_session, strategy, snap_old, "h1")
    # 1 trial on the current snapshot.
    _seed_trial(db_session, strategy, snap_new, "h9")
    # Two PBO runs (old failed, newest passed) + one DSR run.
    _seed_validation_run(db_session, strategy, kind="PBO", created_at=_ts(2026, 1, 1), passed=False)
    _seed_validation_run(db_session, strategy, kind="PBO", created_at=_ts(2026, 2, 1), passed=True)
    _seed_validation_run(db_session, strategy, kind="DSR", created_at=_ts(2026, 1, 15))
    db_session.commit()
    return strategy, {"old": snap_old, "new": snap_new}


def test_context_grouping_duplicates_supersede_and_gates(db_session) -> None:
    strategy, snaps = _seed_strategy_with_history(db_session)

    context = build_context(db_session, "strategy", strategy.id)

    assert context is not None
    assert context["resource"] == "strategy"
    assert context["backtest"] is None
    assert context["strategy_id"] == strategy.id
    assert context["strategy_name"] == "SPY 200DMA"
    assert context["strategy_status"] == "BACKTESTED"
    assert context["family_id"] == strategy.id
    assert context["latest_version"] == 1
    assert context["total_trials"] == 4

    by_snapshot = {row["data_snapshot_id"]: row for row in context["by_snapshot"]}
    old = by_snapshot[snaps["old"].id]
    new = by_snapshot[snaps["new"].id]
    assert old["snapshot_key"] == "spy-daily-20260831-1209a3"
    assert old["superseded_by_key"] == "spy-daily-20260901-1209a3"
    assert old["count"] == 3
    assert old["duplicate_parameter_hashes"] == 1
    assert new["superseded_by_key"] is None
    assert new["count"] == 1
    assert new["duplicate_parameter_hashes"] == 0

    # Gates: canonical kind order, latest run per kind only.
    assert [g["kind"] for g in context["gates"]] == ["DSR", "PBO"]
    dsr, pbo = context["gates"]
    assert (dsr["status"], dsr["passed"]) == ("COMPLETED", True)
    assert (pbo["status"], pbo["passed"]) == ("COMPLETED", True)
    # sqlite round-trips datetimes naive; compare without tzinfo.
    assert pbo["finished_at"] == _ts(2026, 2, 1).replace(tzinfo=None)


def test_context_skips_empty_family_history(db_session) -> None:
    strategy = _seed_strategy(db_session, name="fresh idea")
    db_session.commit()

    context = build_context(db_session, "strategy", strategy.id)

    assert context is not None
    assert context["total_trials"] == 0
    assert context["by_snapshot"] == []
    assert context["gates"] == []
    assert context["latest_version"] is None


def test_context_missing_strategy_returns_none(db_session) -> None:
    assert build_context(db_session, "strategy", uuid4()) is None


def test_context_backtest_scope_resolves_strategy(db_session) -> None:
    strategy, _ = _seed_strategy_with_history(db_session)
    version = _seed_version(db_session, strategy, version=2)
    backtest = Backtest(
        id=uuid4(),
        strategy_version_id=version.id,
        start_date=date(2024, 1, 1),
        end_date=date(2026, 1, 1),
        status="COMPLETED",
        created_at=_ts(2026, 3, 1),
    )
    db_session.add(backtest)
    db_session.commit()

    context = build_context(db_session, "backtest", backtest.id)

    assert context is not None
    assert context["resource"] == "backtest"
    assert context["strategy_id"] == strategy.id
    assert context["backtest"]["id"] == backtest.id
    assert context["backtest"]["status"] == "COMPLETED"
    assert context["total_trials"] == 4


def test_context_missing_backtest_returns_none(db_session) -> None:
    assert build_context(db_session, "backtest", uuid4()) is None


def test_context_counts_consistent_with_trial_stats(db_session) -> None:
    """Anchor test: copilot grouping must not drift from the trial-stats API."""
    from services.api.services import strategies as strategy_service

    strategy, _ = _seed_strategy_with_history(db_session)

    stats = strategy_service.trial_stats(db_session, strategy.id)
    context = build_context(db_session, "strategy", strategy.id)

    assert context is not None
    assert context["total_trials"] == stats["total_trials"]
    stats_by_id = {row["data_snapshot_id"]: row for row in stats["by_snapshot"]}
    context_by_id = {row["data_snapshot_id"]: row for row in context["by_snapshot"]}
    assert set(stats_by_id) == set(context_by_id)
    for snapshot_id, row in stats_by_id.items():
        mine = context_by_id[snapshot_id]
        assert mine["snapshot_key"] == row["snapshot_key"]
        assert mine["count"] == row["count"]
        assert mine["duplicate_parameter_hashes"] == row["duplicate_parameter_hashes"]


def test_context_endpoint_returns_full_shape(client) -> None:
    session = db_module.SessionLocal()
    try:
        strategy, _snaps = _seed_strategy_with_history(session)
        strategy_id = strategy.id
    finally:
        session.close()

    response = client.get(f"/api/v1/copilot/context?resource=strategy&id={strategy_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy_id"] == str(strategy_id)
    assert payload["strategy_status"] == "BACKTESTED"
    assert payload["total_trials"] == 4
    assert payload["provider"] == {"name": "deepseek", "enabled": False}
    assert payload["resource"] == "strategy"
    assert payload["backtest"] is None
    assert any(row["superseded_by_key"] is not None for row in payload["by_snapshot"])


def test_context_endpoint_404_and_422(client) -> None:
    missing = client.get(f"/api/v1/copilot/context?resource=strategy&id={uuid4()}")
    assert missing.status_code == 404

    invalid = client.get(f"/api/v1/copilot/context?resource=note&id={uuid4()}")
    assert invalid.status_code == 422
