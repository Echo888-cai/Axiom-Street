from __future__ import annotations

from datetime import date
from uuid import uuid4

from services.api.services.backtest_cache import result_fingerprint


def test_fingerprint_is_stable_for_the_same_trial():
    kwargs = dict(
        code="print(1)",
        data_snapshot_id=uuid4(),
        engine_version="quantconnect/lean:16355",
        start_date=date(2018, 1, 1),
        end_date=date(2020, 1, 1),
        benchmark="SPY",
        initial_capital=100_000.0,
        universe=["SPY"],
        universe_id=None,
        parameters={"lookback": 200},
    )
    assert result_fingerprint(**kwargs) == result_fingerprint(**kwargs)


def test_fingerprint_changes_when_code_changes():
    snap = uuid4()
    base = dict(
        data_snapshot_id=snap,
        engine_version="quantconnect/lean:16355",
        start_date=date(2018, 1, 1),
        end_date=date(2020, 1, 1),
        benchmark="SPY",
        initial_capital=100_000.0,
        universe=["SPY"],
        universe_id=None,
        parameters={},
    )
    left = result_fingerprint(code="a = 1", **base)
    right = result_fingerprint(code="a = 2", **base)
    assert left != right
