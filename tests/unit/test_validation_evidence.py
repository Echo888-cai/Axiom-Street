"""Evidence must belong to the current research, not a selection of old wins."""

from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from services.api import db as db_module
from services.api.models import (
    Backtest,
    BacktestStatus,
    DataSnapshot,
    ExperimentTrial,
    Strategy,
    StrategyStatus,
    StrategyVersion,
    ValidationKind,
    ValidationRun,
    ValidationRunStatus,
)
from services.api.services.validation import (
    dsr_trial_set_hash,
    maybe_apply_validated,
)


def _mk_sub(db, *, vid, snapshot_id, anchor, params):
    row = Backtest(
        id=uuid4(),
        strategy_version_id=vid,
        start_date=anchor.start_date,
        end_date=anchor.end_date,
        benchmark=anchor.benchmark,
        initial_capital=anchor.initial_capital,
        status=BacktestStatus.COMPLETED,
        parameters=params,
        data_snapshot_id=snapshot_id,
        universe_snapshot=anchor.universe_snapshot,
        engine_version=anchor.engine_version,
        data_version=anchor.data_version,
    )
    db.add(row)
    db.flush()
    return row


def seed(client):
    result = client.post("/api/v1/strategies", json={"name": "Evidence"}).json()
    sid, vid = UUID(result["id"]), UUID(result["latest_version"]["id"])
    with db_module.SessionLocal() as db:
        strategy = db.get(Strategy, sid)
        strategy.status = StrategyStatus.BACKTESTED
        strategy.family_id = strategy.id
        snapshot = DataSnapshot(
            id=uuid4(), snapshot_key="evidence", provider="fixture", content_sha256="a" * 64
        )
        db.add(snapshot)
        db.flush()
        universe = [{"symbol": "SPY", "effective_from": "2020-01-01", "effective_to": None}]
        backtest = Backtest(
            data_snapshot_id=snapshot.id,
            id=uuid4(),
            strategy_version_id=vid,
            start_date=date(2020, 1, 1),
            end_date=date(2024, 1, 1),
            status=BacktestStatus.COMPLETED,
            parameters={"lookback": 200},
            benchmark="SPY",
            initial_capital=100_000.0,
            universe_snapshot=universe,
            engine_version="quantconnect/lean:16355",
            data_version="abc",
        )
        db.add(backtest)
        db.flush()
        bid = backtest.id
        # Scan sub-backtests share the anchored scope; only the declared axis varies.
        pbo_subs = [
            _mk_sub(db, vid=vid, snapshot_id=snapshot.id, anchor=backtest, params={"lookback": v})
            for v in (100, 200)
        ]
        sens_subs = [
            _mk_sub(db, vid=vid, snapshot_id=snapshot.id, anchor=backtest, params={"lookback": v})
            for v in (100, 150, 200)
        ]
        cost_subs = [
            _mk_sub(
                db,
                vid=vid,
                snapshot_id=snapshot.id,
                anchor=backtest,
                params={"lookback": 200, "slippage_bps": c, "fee_usd": 0.0},
            )
            for c in (0.0, 5.0, 10.0)
        ]
        spa_subs = pbo_subs
        # P1.3c: the family ledger these conclusions were computed from.
        ledger = [(backtest, 0.5), (spa_subs[0], 0.3), (spa_subs[1], 0.8)]
        for trial_backtest, sharpe in ledger:
            db.add(
                ExperimentTrial(
                    backtest_id=trial_backtest.id,
                    data_snapshot_id=snapshot.id,
                    strategy_id=sid,
                    strategy_family=strategy.id,
                    parameters=dict(trial_backtest.parameters or {}),
                    parameter_hash=f"evidence-{trial_backtest.id}",
                    observed_sharpe=sharpe,
                )
            )
        db.flush()
        trial_hash = dsr_trial_set_hash(
            [t for t in db.query(ExperimentTrial).all() if t.observed_sharpe is not None]
        )
        trial_ids = sorted(str(b.id) for b, _ in ledger)
        wf_folds = [
            {
                "index": 0,
                "is_start": "2020-01-01",
                "is_end": "2021-12-31",
                "oos_start": "2022-01-01",
                "oos_end": "2022-12-31",
            },
            {
                "index": 1,
                "is_start": "2020-01-01",
                "is_end": "2022-12-31",
                "oos_start": "2023-01-01",
                "oos_end": "2023-12-31",
            },
        ]
        wf_execution = {
            "engine_version": backtest.engine_version,
            "data_version": backtest.data_version,
            "data_snapshot_id": str(snapshot.id),
            "benchmark": backtest.benchmark,
            "initial_capital": backtest.initial_capital,
            "universe_snapshot": universe,
            "parameters": {"lookback": 200},
            "folds": wf_folds,
        }
        per_kind: dict[ValidationKind, tuple[dict, dict]] = {
            ValidationKind.WALK_FORWARD: (
                {
                    "start_date": "2020-01-01",
                    "end_date": "2024-01-01",
                    "benchmark": "SPY",
                    "initial_capital": 100_000.0,
                    "folds": wf_folds,
                },
                {"folds": wf_folds, "execution": wf_execution, "passed": True},
            ),
            ValidationKind.DSR: (
                {
                    "n_obs": 500,
                    "n_trials": len(ledger),
                    "family_id": str(strategy.id),
                    "data_snapshot_id": str(snapshot.id),
                    "trial_set_hash": trial_hash,
                },
                {"dsr": 0.99, "passed": True},
            ),
            ValidationKind.PBO: (
                {
                    "parameter_key": "lookback",
                    "values": [100, 200],
                    "start_date": "2020-01-01",
                    "end_date": "2024-01-01",
                },
                {"backtest_ids": [str(r.id) for r in pbo_subs], "pbo": 0.2, "passed": True},
            ),
            ValidationKind.SENSITIVITY: (
                {
                    "parameter_key": "lookback",
                    "values": [100, 150, 200],
                    "start_date": "2020-01-01",
                    "end_date": "2024-01-01",
                },
                {"backtest_ids": [str(r.id) for r in sens_subs], "passed": True},
            ),
            ValidationKind.COST: (
                {
                    "costs_bps": [0.0, 5.0, 10.0],
                    "start_date": "2020-01-01",
                    "end_date": "2024-01-01",
                },
                {"backtest_ids": [str(r.id) for r in cost_subs], "passed": True},
            ),
            ValidationKind.SPA: (
                {
                    "family_id": str(strategy.id),
                    "data_snapshot_id": str(snapshot.id),
                    "n_models": len(spa_subs),
                    "trial_candidate_ids": trial_ids,
                },
                {
                    "models": [{"backtest_id": str(r.id)} for r in spa_subs],
                    "passed": True,
                },
            ),
        }
        for kind in ValidationKind:
            params, run_result = per_kind.get(kind, ({}, {"passed": True}))
            db.add(
                ValidationRun(
                    strategy_id=sid,
                    strategy_version_id=vid,
                    backtest_id=bid,
                    kind=kind,
                    passed=True,
                    status=ValidationRunStatus.COMPLETED,
                    params=params,
                    result=run_result,
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


def _latest(db, sid, vid, kind):
    from sqlalchemy import select

    return db.scalars(
        select(ValidationRun)
        .where(
            ValidationRun.strategy_id == sid,
            ValidationRun.strategy_version_id == vid,
            ValidationRun.kind == kind,
        )
        .order_by(ValidationRun.created_at.desc())
    ).first()


def test_scan_sub_backtest_with_different_engine_is_rejected(client):
    sid, vid, bid = seed(client)
    assert apply(sid, vid) == StrategyStatus.VALIDATED
    with db_module.SessionLocal() as db:
        pbo = _latest(db, sid, vid, ValidationKind.PBO)
        sub = db.get(Backtest, UUID(pbo.result["backtest_ids"][0]))
        sub.engine_version = "quantconnect/lean:other-image"
        db.commit()
    assert apply(sid, vid) == StrategyStatus.BACKTESTED
    body = client.get(f"/api/v1/live/readiness?strategy_id={sid}").json()
    assert "PBO" in body["evidence"]["missing_validation"]
    assert body["evidence"]["validation_reasons"]["PBO"] == "scan_execution_mismatch"


def test_scan_sub_backtest_with_different_snapshot_is_rejected(client):
    sid, vid, _ = seed(client)
    with db_module.SessionLocal() as db:
        pbo = _latest(db, sid, vid, ValidationKind.PBO)
        sub = db.get(Backtest, UUID(pbo.result["backtest_ids"][0]))
        sub.data_snapshot_id = uuid4()
        db.commit()
    assert apply(sid, vid) == StrategyStatus.BACKTESTED


def test_scan_sub_backtest_with_off_axis_param_change_is_rejected(client):
    sid, vid, _ = seed(client)
    with db_module.SessionLocal() as db:
        sens = _latest(db, sid, vid, ValidationKind.SENSITIVITY)
        sub = db.get(Backtest, UUID(sens.result["backtest_ids"][0]))
        sub.parameters = {"lookback": 100, "extra_universe": "QQQ"}
        db.commit()
    assert apply(sid, vid) == StrategyStatus.BACKTESTED
    with db_module.SessionLocal() as db:
        assert _latest(db, sid, vid, ValidationKind.PBO).passed is True


def test_scan_with_missing_sub_record_is_rejected(client):
    sid, vid, _ = seed(client)
    with db_module.SessionLocal() as db:
        cost = _latest(db, sid, vid, ValidationKind.COST)
        missing = uuid4()
        result = dict(cost.result or {})
        result["backtest_ids"] = [*result["backtest_ids"], str(missing)]
        cost.result = result
        db.commit()
    assert apply(sid, vid) == StrategyStatus.BACKTESTED


def test_scan_with_empty_backtest_ids_needs_revalidation(client):
    sid, vid, _ = seed(client)
    with db_module.SessionLocal() as db:
        pbo = _latest(db, sid, vid, ValidationKind.PBO)
        pbo.result = {"pbo": 0.2, "passed": True}
        db.commit()
    assert apply(sid, vid) == StrategyStatus.BACKTESTED
    body = client.get(f"/api/v1/live/readiness?strategy_id={sid}").json()
    assert body["evidence"]["validation_reasons"]["PBO"] == "scan_execution_missing"


def test_walk_forward_without_execution_evidence_needs_revalidation(client):
    sid, vid, _ = seed(client)
    with db_module.SessionLocal() as db:
        wf = _latest(db, sid, vid, ValidationKind.WALK_FORWARD)
        result = dict(wf.result or {})
        result.pop("execution", None)
        wf.result = result
        db.commit()
    assert apply(sid, vid) == StrategyStatus.BACKTESTED
    body = client.get(f"/api/v1/live/readiness?strategy_id={sid}").json()
    assert body["evidence"]["validation_reasons"]["WALK_FORWARD"] == (
        "walk_forward_execution_missing"
    )


def test_walk_forward_with_swapped_snapshot_is_rejected(client):
    sid, vid, _ = seed(client)
    with db_module.SessionLocal() as db:
        wf = _latest(db, sid, vid, ValidationKind.WALK_FORWARD)
        result = dict(wf.result or {})
        execution = dict(result["execution"])
        execution["data_snapshot_id"] = str(uuid4())
        result["execution"] = execution
        wf.result = result
        db.commit()
    assert apply(sid, vid) == StrategyStatus.BACKTESTED


def test_spa_with_missing_trial_is_rejected(client):
    sid, vid, _ = seed(client)
    with db_module.SessionLocal() as db:
        spa = _latest(db, sid, vid, ValidationKind.SPA)
        result = dict(spa.result or {})
        result["models"] = [*result["models"], {"backtest_id": str(uuid4())}]
        params = dict(spa.params or {})
        params["n_models"] = len(result["models"])
        spa.result = result
        spa.params = params
        db.commit()
    assert apply(sid, vid) == StrategyStatus.BACKTESTED


def test_spa_with_cross_snapshot_trial_is_rejected(client):
    sid, vid, _ = seed(client)
    with db_module.SessionLocal() as db:
        spa = _latest(db, sid, vid, ValidationKind.SPA)
        other = Backtest(
            id=uuid4(),
            strategy_version_id=vid,
            start_date=date(2020, 1, 1),
            end_date=date(2024, 1, 1),
            status=BacktestStatus.COMPLETED,
            parameters={},
            data_snapshot_id=uuid4(),
        )
        db.add(other)
        db.flush()
        result = dict(spa.result or {})
        models = [dict(item) for item in result["models"]]
        models[0] = {"backtest_id": str(other.id)}
        result["models"] = models
        spa.result = result
        db.commit()
    assert apply(sid, vid) == StrategyStatus.BACKTESTED


def _add_trial(db, *, sid, vid, snapshot_id, sharpe: float) -> None:
    from services.api.models import Strategy as _Strategy

    strategy = db.get(_Strategy, sid)
    row = Backtest(
        id=uuid4(),
        strategy_version_id=vid,
        start_date=date(2020, 1, 1),
        end_date=date(2024, 1, 1),
        status=BacktestStatus.COMPLETED,
        parameters={"lookback": 300},
        data_snapshot_id=snapshot_id,
        engine_version="quantconnect/lean:16355",
        data_version="abc",
    )
    db.add(row)
    db.flush()
    db.add(
        ExperimentTrial(
            backtest_id=row.id,
            data_snapshot_id=snapshot_id,
            strategy_id=sid,
            strategy_family=strategy.family_id,
            parameters={"lookback": 300},
            parameter_hash=f"extra-{row.id}",
            observed_sharpe=sharpe,
        )
    )
    db.commit()


def test_new_trial_expires_dsr_and_spa_until_recomputed(client):
    sid, vid, bid = seed(client)
    assert apply(sid, vid) == StrategyStatus.VALIDATED
    with db_module.SessionLocal() as db:
        anchor = db.get(Backtest, bid)
        assert anchor is not None
        _add_trial(db, sid=sid, vid=vid, snapshot_id=anchor.data_snapshot_id, sharpe=1.5)
    assert apply(sid, vid) == StrategyStatus.BACKTESTED
    body = client.get(f"/api/v1/live/readiness?strategy_id={sid}").json()
    missing = body["evidence"]["missing_validation"]
    assert "DSR" in missing
    assert "SPA" in missing
    assert body["evidence"]["validation_reasons"]["DSR"] == "dsr_trial_set_changed"
    assert body["evidence"]["validation_reasons"]["SPA"] == "spa_trial_set_changed"


def test_sharpe_update_without_new_row_expires_dsr_only(client):
    """Trial sharpe lands at backtest completion; a value change with the same
    row count must still expire DSR (hash covers values, not just counts)."""
    sid, vid, bid = seed(client)
    assert apply(sid, vid) == StrategyStatus.VALIDATED
    with db_module.SessionLocal() as db:
        trial = db.query(ExperimentTrial).filter(ExperimentTrial.backtest_id == bid).one()
        trial.observed_sharpe = 2.5
        db.commit()
    assert apply(sid, vid) == StrategyStatus.BACKTESTED
    with db_module.SessionLocal() as db:
        from services.api.services.validation_evidence import collect_validation_evidence

        evidence = collect_validation_evidence(db, strategy_id=sid, strategy_version_id=vid)
        assert evidence.reasons["DSR"] == "dsr_trial_set_changed"
        assert "SPA" not in evidence.reasons


def test_recomputed_dsr_and_spa_revalidate_on_new_generation(client):
    from services.api.services.validation import (
        dsr_trial_rows,
        dsr_trial_set_hash,
        spa_candidate_ids,
    )

    sid, vid, bid = seed(client)
    with db_module.SessionLocal() as db:
        anchor = db.get(Backtest, bid)
        assert anchor is not None
        snapshot_id = anchor.data_snapshot_id
        assert snapshot_id is not None
        strategy = db.get(Strategy, sid)
        assert strategy is not None
        _add_trial(db, sid=sid, vid=vid, snapshot_id=snapshot_id, sharpe=1.5)
        trials = dsr_trial_rows(db, family_id=strategy.family_id, snapshot_id=snapshot_id)
        candidates = spa_candidate_ids(db, family_id=strategy.family_id, snapshot_id=snapshot_id)
        dsr = _latest(db, sid, vid, ValidationKind.DSR)
        dsr.params = {
            **(dsr.params or {}),
            "n_trials": max(sum(1 for t in trials if t.observed_sharpe is not None), 1),
            "trial_set_hash": dsr_trial_set_hash(trials),
        }
        spa = _latest(db, sid, vid, ValidationKind.SPA)
        spa.params = {
            **(spa.params or {}),
            "n_models": len(candidates),
            "trial_candidate_ids": candidates,
        }
        spa.result = {"models": [{"backtest_id": c} for c in candidates], "passed": True}
        db.commit()
    assert apply(sid, vid) == StrategyStatus.VALIDATED


def test_dsr_count_fallback_catches_added_trials_without_hash(client):
    sid, vid, bid = seed(client)
    with db_module.SessionLocal() as db:
        dsr = _latest(db, sid, vid, ValidationKind.DSR)
        params = dict(dsr.params or {})
        params.pop("trial_set_hash", None)
        params["n_trials"] = 3
        dsr.params = params
        db.commit()
    assert apply(sid, vid) == StrategyStatus.VALIDATED
    with db_module.SessionLocal() as db:
        anchor = db.get(Backtest, bid)
        assert anchor is not None
        _add_trial(db, sid=sid, vid=vid, snapshot_id=anchor.data_snapshot_id, sharpe=0.1)
    assert apply(sid, vid) == StrategyStatus.BACKTESTED


def test_spa_without_baseline_is_left_to_scope_checks(client):
    """Pre-generation SPA rows carry no candidate list and cannot be
    generation-checked; scope and model-existence checks still apply.
    Re-run SPA to gain binding."""
    sid, vid, _ = seed(client)
    with db_module.SessionLocal() as db:
        spa = _latest(db, sid, vid, ValidationKind.SPA)
        params = dict(spa.params or {})
        params.pop("trial_candidate_ids", None)
        spa.params = params
        db.commit()
    assert apply(sid, vid) == StrategyStatus.VALIDATED


def test_other_snapshot_trials_do_not_expire_current_evidence(client):
    sid, vid, bid = seed(client)
    assert apply(sid, vid) == StrategyStatus.VALIDATED
    with db_module.SessionLocal() as db:
        _add_trial(db, sid=sid, vid=vid, snapshot_id=uuid4(), sharpe=3.0)
    assert apply(sid, vid) == StrategyStatus.VALIDATED


def test_evidence_endpoint_reports_per_kind_status_and_reference(client):
    sid, vid, bid = seed(client)
    res = client.get(f"/api/v1/validation/evidence?strategy_id={sid}&strategy_version_id={vid}")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["strategy_id"] == str(sid)
    assert body["strategy_version_id"] == str(vid)
    assert body["backtest_id"] == str(bid)
    assert body["reasons"] == {}
    assert len(body["passed"]) == len(ValidationKind)
    assert all(body["passed"].values())


def test_evidence_endpoint_shows_expiry_reason_after_new_trial(client):
    sid, vid, bid = seed(client)
    with db_module.SessionLocal() as db:
        anchor = db.get(Backtest, bid)
        assert anchor is not None
        _add_trial(db, sid=sid, vid=vid, snapshot_id=anchor.data_snapshot_id, sharpe=1.5)
    res = client.get(f"/api/v1/validation/evidence?strategy_id={sid}&strategy_version_id={vid}")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["passed"]["DSR"] is False
    assert body["reasons"]["DSR"] == "dsr_trial_set_changed"
    assert body["passed"]["SPA"] is False
    assert body["reasons"]["SPA"] == "spa_trial_set_changed"
