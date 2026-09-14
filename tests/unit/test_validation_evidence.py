"""Evidence must belong to the current research, not a selection of old wins."""

from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from services.api import db as db_module
from services.api.models import (
    Backtest,
    BacktestStatus,
    DataSnapshot,
    Strategy,
    StrategyStatus,
    StrategyVersion,
    ValidationKind,
    ValidationRun,
    ValidationRunStatus,
)
from services.api.services.validation import maybe_apply_validated


def seed(client):
    result = client.post("/api/v1/strategies", json={"name": "Evidence"}).json()
    sid, vid = UUID(result["id"]), UUID(result["latest_version"]["id"])
    with db_module.SessionLocal() as db:
        strategy = db.get(Strategy, sid)
        strategy.status = StrategyStatus.BACKTESTED
        snapshot = DataSnapshot(
            id=uuid4(), snapshot_key="evidence", provider="fixture", content_sha256="a" * 64
        )
        db.add(snapshot)
        db.flush()
        backtest = Backtest(
            data_snapshot_id=snapshot.id,
            id=uuid4(),
            strategy_version_id=vid,
            start_date=date(2020, 1, 1),
            end_date=date(2024, 1, 1),
            status=BacktestStatus.COMPLETED,
            parameters={"lookback": 200},
        )
        db.add(backtest)
        db.flush()
        bid = backtest.id
        for kind in ValidationKind:
            db.add(
                ValidationRun(
                    strategy_id=sid,
                    strategy_version_id=vid,
                    backtest_id=bid,
                    kind=kind,
                    passed=True,
                    status=ValidationRunStatus.COMPLETED,
                    created_at=datetime.now(timezone.utc) - timedelta(days=1),
                )
            )
        db.commit()
    return sid, vid, bid


def apply(sid, vid):
    with db_module.SessionLocal() as db:
        maybe_apply_validated(db, strategy_id=sid, strategy_version_id=vid)
        db.commit()
        return db.get(Strategy, sid).status


@pytest.mark.parametrize(
    "state",
    [
        ValidationRunStatus.FAILED,
        ValidationRunStatus.QUEUED,
        ValidationRunStatus.RUNNING,
        ValidationRunStatus.COMPLETED,
    ],
)
def test_latest_nonpassing_run_blocks_old_success_in_both_consumers(client, state):
    sid, vid, bid = seed(client)
    assert apply(sid, vid) == StrategyStatus.VALIDATED
    with db_module.SessionLocal() as db:
        db.add(
            ValidationRun(
                strategy_id=sid,
                strategy_version_id=vid,
                backtest_id=bid,
                kind=ValidationKind.PBO,
                status=state,
                passed=False,
            )
        )
        db.commit()
    response = client.get(f"/api/v1/live/readiness?strategy_id={sid}")
    assert response.status_code == 200
    assert "PBO" in response.json()["evidence"]["missing_validation"]
    assert apply(sid, vid) == StrategyStatus.BACKTESTED


def test_old_version_completion_cannot_validate_current_version(client):
    sid, vid, _ = seed(client)
    with db_module.SessionLocal() as db:
        db.add(StrategyVersion(strategy_id=sid, version=2, code="new code", config={}))
        db.commit()
    assert apply(sid, vid) == StrategyStatus.BACKTESTED


@pytest.mark.parametrize(
    "changed",
    [
        "data_snapshot_id",
        "parameters",
        "start_date",
        "benchmark",
        "initial_capital",
        "engine_version",
    ],
)
def test_cannot_combine_validation_results_from_different_research_inputs(client, changed):
    sid, vid, bid = seed(client)
    with db_module.SessionLocal() as db:
        original = db.get(Backtest, bid)
        other = Backtest(
            id=uuid4(),
            strategy_version_id=vid,
            start_date=original.start_date,
            end_date=original.end_date,
            status=BacktestStatus.COMPLETED,
            parameters=original.parameters,
            data_snapshot_id=original.data_snapshot_id,
            benchmark=original.benchmark,
            initial_capital=original.initial_capital,
        )
        value = {
            "data_snapshot_id": uuid4(),
            "parameters": {"lookback": 50},
            "start_date": date(2021, 1, 1),
            "benchmark": "QQQ",
            "initial_capital": 42,
            "engine_version": "different",
        }[changed]
        setattr(other, changed, value)
        db.add(other)
        db.flush()
        db.add(
            ValidationRun(
                strategy_id=sid,
                strategy_version_id=vid,
                backtest_id=other.id,
                kind=ValidationKind.COST,
                passed=True,
                status=ValidationRunStatus.COMPLETED,
            )
        )
        db.commit()
    assert apply(sid, vid) == StrategyStatus.BACKTESTED
    body = client.get(f"/api/v1/live/readiness?strategy_id={sid}").json()
    assert "COST" in body["evidence"]["missing_validation"]


def test_failed_worker_validation_revokes_validated_status(client):
    from services.worker.tasks.scans import _fail_walk_forward

    sid, vid, bid = seed(client)
    assert apply(sid, vid) == StrategyStatus.VALIDATED
    with db_module.SessionLocal() as db:
        run = ValidationRun(
            strategy_id=sid,
            strategy_version_id=vid,
            backtest_id=bid,
            kind=ValidationKind.PBO,
            status=ValidationRunStatus.RUNNING,
        )
        db.add(run)
        db.flush()
        _fail_walk_forward(db, run, "worker_failed", "interrupted")
        assert db.get(Strategy, sid).status == StrategyStatus.BACKTESTED


def test_old_version_callback_does_not_revoke_current_validation(client):
    sid, vid, _ = seed(client)
    with db_module.SessionLocal() as db:
        db.add(StrategyVersion(strategy_id=sid, version=2, code="new code", config={}))
        db.get(Strategy, sid).status = StrategyStatus.VALIDATED
        db.commit()
    assert apply(sid, vid) == StrategyStatus.VALIDATED


@pytest.mark.parametrize("missing", ["snapshot", "source", "window"])
def test_incomplete_or_shortened_evidence_cannot_validate(client, missing):
    sid, vid, bid = seed(client)
    with db_module.SessionLocal() as db:
        if missing == "snapshot":
            db.get(Backtest, bid).data_snapshot_id = None
        else:
            db.add(
                ValidationRun(
                    strategy_id=sid,
                    strategy_version_id=vid,
                    backtest_id=None if missing == "source" else bid,
                    kind=ValidationKind.COST,
                    passed=True,
                    params={"start_date": "2023-01-01"} if missing == "window" else {},
                    status=ValidationRunStatus.COMPLETED,
                )
            )
        db.commit()
    assert apply(sid, vid) == StrategyStatus.BACKTESTED


@pytest.mark.parametrize(
    "kind", [ValidationKind.PBO, ValidationKind.SENSITIVITY, ValidationKind.COST]
)
def test_scan_preparation_inherits_reference_research_scope(client, kind):
    from services.api.services.validation_spec import get_spec

    sid, vid, bid = seed(client)
    with db_module.SessionLocal() as db:
        template = db.get(Backtest, bid)
        template.benchmark = "QQQ"
        template.initial_capital = 12345
        template.universe_snapshot = [{"symbol": "QQQ"}]
        spec = get_spec(kind)
        supplied = {"values": [100, 200]} if kind == ValidationKind.PBO else {}
        params = spec.prepare_params(
            db,
            db.get(StrategyVersion, vid),
            template,
            spec.params_schema().model_validate(supplied),
        )
        assert params["start_date"] == template.start_date.isoformat()
        assert params["end_date"] == template.end_date.isoformat()
        assert params["data_snapshot_id"] == str(template.data_snapshot_id)
        assert params["base_parameters"] == {"lookback": 200}
        assert params["benchmark"] == "QQQ"
        assert params["initial_capital"] == 12345
        assert params["universe_snapshot"] == [{"symbol": "QQQ"}]
