"""Deterministic suggestion derivation (P5-3)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.db import Base
from services.api.models import (
    Backtest,
    DataSnapshot,
    ExperimentTrial,
    Strategy,
    StrategyVersion,
    ValidationRun,
)
from services.agent.suggestions import CARD_KEYS, derive_suggestions


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


def _seed_strategy(db_session, *, name: str = "SPY 200DMA", status: str = "BACKTESTED"):
    strategy = Strategy(id=uuid4(), name=name, status=status, benchmark="SPY")
    db_session.add(strategy)
    return strategy


def _code(*, lookback: bool = True, slippage: bool = True) -> str:
    lines = ["class A(QCAlgorithm):", "    def Initialize(self):"]
    if lookback:
        lines.append('        self.lookback = int(self.GetParameter("lookback"))')
    if slippage:
        lines.append('        self.sp = self.GetParameter("slippage_bps")')
    return "\n".join(lines)


def _seed_version(db_session, strategy: Strategy, version: int = 1, code: str | None = None):
    row = StrategyVersion(
        id=uuid4(),
        strategy_id=strategy.id,
        version=version,
        code=code if code is not None else _code(),
        config={},
        commit_message=f"v{version}",
    )
    db_session.add(row)
    return row


def _seed_completed_backtest(db_session, version: StrategyVersion, *, created: datetime):
    backtest = Backtest(
        id=uuid4(),
        strategy_version_id=version.id,
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
        status="COMPLETED",
        parameters={},
        created_at=created,
    )
    db_session.add(backtest)
    return backtest


def _seed_run(
    db_session,
    strategy: Strategy,
    version: StrategyVersion,
    *,
    kind: str,
    created: datetime,
    passed: bool = True,
    status: str = "COMPLETED",
):
    row = ValidationRun(
        id=uuid4(),
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        kind=kind,
        status=status,
        passed=passed,
        created_at=created,
        finished_at=created,
    )
    db_session.add(row)
    return row


def _seed_snapshot(db_session, key: str, *, superseded_by: DataSnapshot | None = None):
    row = DataSnapshot(
        id=uuid4(),
        snapshot_key=key,
        provider="polygon",
        content_sha256="0" * 64,
        superseded_by=superseded_by.id if superseded_by else None,
    )
    db_session.add(row)
    return row


def _seed_trial(db_session, strategy: Strategy, snapshot: DataSnapshot | None, hash_: str):
    row = ExperimentTrial(
        id=uuid4(),
        strategy_id=strategy.id,
        strategy_family=strategy.id,
        data_snapshot_id=snapshot.id if snapshot else None,
        universe_key="SPY",
        parameter_hash=hash_,
        is_oos=False,
    )
    db_session.add(row)
    return row


def test_missing_strategy_and_no_versions_are_empty(db_session) -> None:
    assert derive_suggestions(db_session, uuid4()) == []
    strategy = _seed_strategy(db_session)
    db_session.commit()
    assert derive_suggestions(db_session, strategy.id) == []


def test_no_completed_backtest_yields_only_guide_card(db_session) -> None:
    strategy = _seed_strategy(db_session)
    version = _seed_version(db_session, strategy)
    db_session.commit()

    cards = derive_suggestions(db_session, strategy.id)

    assert len(cards) == 1
    assert cards[0]["action"] == "guide"
    assert cards[0]["reason_code"] == "backtest_first"
    assert cards[0]["executable"] is False
    assert cards[0]["strategy_version_id"] == version.id


def test_open_gates_yield_run_cards_for_eligible_kinds(db_session) -> None:
    strategy = _seed_strategy(db_session)
    version = _seed_version(db_session, strategy)  # reads lookback + slippage
    _seed_completed_backtest(db_session, version, created=_ts(2026, 1, 1))
    db_session.commit()

    cards = derive_suggestions(db_session, strategy.id)
    runnable = [c for c in cards if c["action"] == "run_validation"]

    # All non-DSR kinds are open and eligible for a lookback+slippage strategy.
    kinds = {c["validation_kind"] for c in runnable}
    assert kinds == {
        "WALK_FORWARD",
        "PBO",
        "SENSITIVITY",
        "COST",
        "BOOTSTRAP",
        "REGIME",
        "SPA",
    }
    assert all(c["executable"] for c in runnable)
    assert all(c["reason_code"] == "never_run" for c in runnable)
    assert all(c["strategy_version_id"] == version.id for c in runnable)
    # Every run card templates from the same latest completed backtest.
    assert len({c["template_backtest_id"] for c in runnable}) == 1

    # DSR is never a card.
    assert "DSR" not in kinds


def test_passed_gate_is_not_suggested(db_session) -> None:
    strategy = _seed_strategy(db_session)
    version = _seed_version(db_session, strategy)
    _seed_completed_backtest(db_session, version, created=_ts(2026, 1, 1))
    _seed_run(
        db_session, strategy, version, kind="WALK_FORWARD", created=_ts(2026, 1, 2), passed=True
    )
    db_session.commit()

    kinds = {c["validation_kind"] for c in derive_suggestions(db_session, strategy.id)}
    assert "WALK_FORWARD" not in kinds
    assert "PBO" in kinds


def test_failed_gate_is_suggested_as_not_passed(db_session) -> None:
    strategy = _seed_strategy(db_session)
    version = _seed_version(db_session, strategy)
    _seed_completed_backtest(db_session, version, created=_ts(2026, 1, 1))
    _seed_run(
        db_session, strategy, version, kind="WALK_FORWARD", created=_ts(2026, 1, 2), passed=False
    )
    db_session.commit()

    wf = next(
        c
        for c in derive_suggestions(db_session, strategy.id)
        if c.get("validation_kind") == "WALK_FORWARD"
    )
    assert wf["reason_code"] == "not_passed"


def test_inflight_gate_is_not_suggested(db_session) -> None:
    strategy = _seed_strategy(db_session)
    version = _seed_version(db_session, strategy)
    _seed_completed_backtest(db_session, version, created=_ts(2026, 1, 1))
    _seed_run(db_session, strategy, version, kind="PBO", created=_ts(2026, 1, 2), status="QUEUED")
    db_session.commit()

    kinds = {c.get("validation_kind") for c in derive_suggestions(db_session, strategy.id)}
    assert "PBO" not in kinds


def test_scan_kinds_need_the_strategy_to_read_the_param(db_session) -> None:
    strategy = _seed_strategy(db_session)
    version = _seed_version(db_session, strategy, code=_code(lookback=False, slippage=False))
    _seed_completed_backtest(db_session, version, created=_ts(2026, 1, 1))
    db_session.commit()

    kinds = {c.get("validation_kind") for c in derive_suggestions(db_session, strategy.id)}
    assert "PBO" not in kinds
    assert "SENSITIVITY" not in kinds
    assert "COST" not in kinds
    assert {"WALK_FORWARD", "BOOTSTRAP", "REGIME", "SPA"} <= kinds


def test_suggestions_are_latest_version_scoped(db_session) -> None:
    strategy = _seed_strategy(db_session)
    v1 = _seed_version(db_session, strategy, version=1)
    _seed_completed_backtest(db_session, v1, created=_ts(2025, 1, 1))
    _seed_run(db_session, strategy, v1, kind="WALK_FORWARD", created=_ts(2025, 1, 2), passed=True)
    v2 = _seed_version(db_session, strategy, version=2)
    _seed_completed_backtest(db_session, v2, created=_ts(2026, 1, 1))
    db_session.commit()

    runnable = [
        c for c in derive_suggestions(db_session, strategy.id) if c["action"] == "run_validation"
    ]
    # The old version's passing WF does not clear the new version's gate.
    wf = next(c for c in runnable if c["validation_kind"] == "WALK_FORWARD")
    assert wf["strategy_version_id"] == v2.id
    assert wf["target_version"] == 2


def test_discipline_cards_for_superseded_and_duplicate_trials(db_session) -> None:
    strategy = _seed_strategy(db_session)
    _seed_version(db_session, strategy)
    snap_new = _seed_snapshot(db_session, "snap-new")
    snap_old = _seed_snapshot(db_session, "snap-old", superseded_by=snap_new)
    _seed_trial(db_session, strategy, snap_old, "h1")
    _seed_trial(db_session, strategy, snap_old, "h1")  # duplicate on superseded snapshot
    db_session.commit()

    reasons = {c["reason_code"] for c in derive_suggestions(db_session, strategy.id)}
    assert "superseded_snapshot" in reasons
    assert "duplicate_parameters" in reasons


def test_archived_strategy_yields_no_cards(db_session) -> None:
    strategy = _seed_strategy(db_session, status="ARCHIVED")
    _seed_version(db_session, strategy)
    db_session.commit()
    assert derive_suggestions(db_session, strategy.id) == []


def test_cards_only_carry_whitelisted_keys(db_session) -> None:
    strategy = _seed_strategy(db_session)
    version = _seed_version(db_session, strategy)
    _seed_completed_backtest(db_session, version, created=_ts(2026, 1, 1))
    snap = _seed_snapshot(db_session, "snap")
    _seed_trial(db_session, strategy, snap, "h1")
    db_session.commit()

    for card in derive_suggestions(db_session, strategy.id):
        assert set(card) <= CARD_KEYS
        assert card["reason_code"] in {
            "never_run",
            "not_passed",
            "backtest_first",
            "superseded_snapshot",
            "duplicate_parameters",
        }
