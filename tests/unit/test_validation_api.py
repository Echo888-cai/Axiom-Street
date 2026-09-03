from datetime import date
from uuid import UUID

from services.api.models import Backtest, BacktestStatus
from services.api.schemas import CostScanCreate, SensitivityCreate, WalkForwardCreate


def test_validation_list_exposes_gates(client):
    res = client.get("/api/v1/validation")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 0
    assert "WALK_FORWARD" in body["gates"]["validated_requires"]
    assert "PBO" in body["gates"]["validated_requires"]
    assert "SENSITIVITY" in body["gates"]["validated_requires"]
    assert "COST" in body["gates"]["validated_requires"]
    assert "DSR" in body["gates"]["available"]
    assert "WALK_FORWARD" in body["gates"]["available"]
    assert "PBO" in body["gates"]["available"]
    assert "SENSITIVITY" in body["gates"]["available"]
    assert "COST" in body["gates"]["available"]
    assert "WALK_FORWARD" not in body["gates"]["missing"]
    assert "PBO" not in body["gates"]["missing"]
    assert "SENSITIVITY" not in body["gates"]["missing"]
    assert "COST" not in body["gates"]["missing"]
    assert "BOOTSTRAP" in body["gates"]["missing"]


def test_walk_forward_requires_completed_backtest(client):
    created = client.post("/api/v1/strategies", json={"name": "wf-empty"}).json()
    res = client.post(
        "/api/v1/validation/walk-forward",
        json={
            "strategy_version_id": created["latest_version"]["id"],
            "train_years": 1,
            "test_years": 1,
            "start_date": "2018-01-01",
            "end_date": "2020-12-31",
        },
    )
    assert res.status_code == 409, res.text
    assert "全样本回测" in res.json()["detail"]


def _completed_backtest(strategy_version_id: str) -> None:
    from services.api.db import SessionLocal

    db = SessionLocal()
    db.add(
        Backtest(
            strategy_version_id=UUID(strategy_version_id),
            start_date=date(2018, 1, 1),
            end_date=date(2020, 12, 31),
            status=BacktestStatus.COMPLETED,
            universe_snapshot=[
                {"symbol": "SPY", "effective_from": "2018-01-01", "effective_to": None}
            ],
        )
    )
    db.commit()
    db.close()


def test_walk_forward_rejects_window_that_cannot_yield_two_folds(client):
    created = client.post("/api/v1/strategies", json={"name": "wf-short"}).json()
    version_id = created["latest_version"]["id"]
    _completed_backtest(version_id)
    res = client.post(
        "/api/v1/validation/walk-forward",
        json={
            "strategy_version_id": version_id,
            "train_years": 3,
            "test_years": 1,
            "start_date": "2018-01-01",
            "end_date": "2020-12-31",
        },
    )
    assert res.status_code == 400, res.text
    assert "至少需要 2 折" in res.json()["detail"]


def test_walk_forward_enqueues(client):
    created = client.post("/api/v1/strategies", json={"name": "wf-ok"}).json()
    version_id = created["latest_version"]["id"]
    _completed_backtest(version_id)
    res = client.post(
        "/api/v1/validation/walk-forward",
        json={
            "strategy_version_id": version_id,
            "train_years": 1,
            "test_years": 1,
            "mode": "rolling",
            "start_date": "2018-01-01",
            "end_date": "2020-12-31",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["kind"] == "WALK_FORWARD"
    assert body["status"] == "QUEUED"
    assert len(body["params"]["folds"]) == 2
    listed = client.get("/api/v1/validation")
    assert listed.json()["total"] == 1
    got = client.get(f"/api/v1/validation/{body['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == body["id"]


def test_pbo_requires_lookback_in_code(client):
    created = client.post("/api/v1/strategies", json={"name": "pbo-no-param"}).json()
    version_id = created["latest_version"]["id"]
    _completed_backtest(version_id)
    without = client.post(
        f"/api/v1/strategies/{created['id']}/versions",
        json={
            "code": "class X:\n    def Initialize(self):\n        self.sma = self.SMA('SPY', 200)\n",
            "commit_message": "hardcoded period",
        },
    )
    assert without.status_code == 201, without.text
    res = client.post(
        "/api/v1/validation/pbo",
        json={"strategy_version_id": without.json()["id"], "values": [100, 200]},
    )
    assert res.status_code == 409, res.text
    assert "lookback" in res.json()["detail"]


def test_pbo_rejects_single_value(client):
    created = client.post("/api/v1/strategies", json={"name": "pbo-one"}).json()
    version_id = created["latest_version"]["id"]
    _completed_backtest(version_id)
    res = client.post(
        "/api/v1/validation/pbo",
        json={"strategy_version_id": version_id, "values": [200, 200]},
    )
    assert res.status_code == 400, res.text
    assert "2–12" in res.json()["detail"]


def test_pbo_enqueues(client):
    created = client.post("/api/v1/strategies", json={"name": "pbo-ok"}).json()
    version_id = created["latest_version"]["id"]
    _completed_backtest(version_id)
    res = client.post(
        "/api/v1/validation/pbo",
        json={
            "strategy_version_id": version_id,
            "values": [100, 150, 200, 250],
            "start_date": "2018-01-01",
            "end_date": "2020-12-31",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["kind"] == "PBO"
    assert body["status"] == "QUEUED"
    assert body["params"]["values"] == [100, 150, 200, 250]
    listed = client.get("/api/v1/validation?kind=PBO")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


def test_walk_forward_create_schema_defaults():
    payload = WalkForwardCreate(strategy_version_id=UUID("00000000-0000-0000-0000-000000000001"))
    assert payload.train_years == 3
    assert payload.test_years == 1
    assert payload.mode == "rolling"
    assert payload.embargo_days == 1


def test_sensitivity_requires_lookback_in_code(client):
    created = client.post("/api/v1/strategies", json={"name": "sens-no-param"}).json()
    version_id = created["latest_version"]["id"]
    _completed_backtest(version_id)
    without = client.post(
        f"/api/v1/strategies/{created['id']}/versions",
        json={
            "code": "class X:\n    def Initialize(self):\n        self.sma = self.SMA('SPY', 200)\n",
            "commit_message": "hardcoded period",
        },
    )
    assert without.status_code == 201, without.text
    res = client.post(
        "/api/v1/validation/sensitivity",
        json={"strategy_version_id": without.json()["id"], "values": [100, 150, 200]},
    )
    assert res.status_code == 409, res.text
    assert "lookback" in res.json()["detail"]


def test_sensitivity_rejects_two_values(client):
    created = client.post("/api/v1/strategies", json={"name": "sens-two"}).json()
    version_id = created["latest_version"]["id"]
    _completed_backtest(version_id)
    res = client.post(
        "/api/v1/validation/sensitivity",
        json={"strategy_version_id": version_id, "values": [100, 200]},
    )
    assert res.status_code == 400, res.text
    assert "3–12" in res.json()["detail"]


def test_sensitivity_enqueues(client):
    created = client.post("/api/v1/strategies", json={"name": "sens-ok"}).json()
    version_id = created["latest_version"]["id"]
    _completed_backtest(version_id)
    res = client.post(
        "/api/v1/validation/sensitivity",
        json={
            "strategy_version_id": version_id,
            "values": [100, 150, 200, 250, 300],
            "start_date": "2018-01-01",
            "end_date": "2020-12-31",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["kind"] == "SENSITIVITY"
    assert body["status"] == "QUEUED"
    assert body["params"]["values"] == [100, 150, 200, 250, 300]


def test_cost_requires_slippage_parameter(client):
    created = client.post("/api/v1/strategies", json={"name": "cost-no-param"}).json()
    version_id = created["latest_version"]["id"]
    _completed_backtest(version_id)
    without = client.post(
        f"/api/v1/strategies/{created['id']}/versions",
        json={
            "code": "class X:\n    def Initialize(self):\n        self.spy.SetSlippageModel(ConstantSlippageModel(0.0005))\n",
            "commit_message": "hardcoded slippage",
        },
    )
    assert without.status_code == 201, without.text
    res = client.post(
        "/api/v1/validation/cost",
        json={"strategy_version_id": without.json()["id"], "costs_bps": [0, 5, 10]},
    )
    assert res.status_code == 409, res.text
    assert "slippage_bps" in res.json()["detail"]


def test_cost_requires_zero_bps(client):
    created = client.post("/api/v1/strategies", json={"name": "cost-no-zero"}).json()
    version_id = created["latest_version"]["id"]
    _completed_backtest(version_id)
    res = client.post(
        "/api/v1/validation/cost",
        json={"strategy_version_id": version_id, "costs_bps": [1, 5, 10]},
    )
    assert res.status_code == 400, res.text
    assert "0 bps" in res.json()["detail"]


def test_cost_enqueues(client):
    created = client.post("/api/v1/strategies", json={"name": "cost-ok"}).json()
    version_id = created["latest_version"]["id"]
    _completed_backtest(version_id)
    res = client.post(
        "/api/v1/validation/cost",
        json={
            "strategy_version_id": version_id,
            "costs_bps": [0, 1, 5, 10],
            "realistic_one_way_bps": 5,
            "start_date": "2018-01-01",
            "end_date": "2020-12-31",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["kind"] == "COST"
    assert body["status"] == "QUEUED"
    assert body["params"]["costs_bps"] == [0, 1, 5, 10]
    assert body["params"]["realistic_one_way_bps"] == 5


def test_sensitivity_and_cost_schema_defaults():
    sid = UUID("00000000-0000-0000-0000-000000000001")
    sens = SensitivityCreate(strategy_version_id=sid)
    assert sens.values == [100, 150, 200, 250, 300]
    cost = CostScanCreate(strategy_version_id=sid)
    assert cost.costs_bps[0] == 0
    assert cost.realistic_one_way_bps == 5.0
