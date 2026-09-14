"""P3.2 acceptance: point-in-time correctness fixtures.

Fixed cases for calendar/execution timing, halts, delisting, renames and
fundamental availability, plus the explicit "unknown validity" marking so a run
never pretends today's constituents were the historical ones.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest


def _frame(rows: list[tuple[str, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime([r[0] for r in rows], utc=True),
            "open": [r[1] for r in rows],
            "high": [r[1] + 1 for r in rows],
            "low": [r[1] - 1 for r in rows],
            "close": [r[1] for r in rows],
            "volume": [1000] * len(rows),
            "stock_splits": [0.0] * len(rows),
            "dividends": [0.0] * len(rows),
        }
    )


def test_calendar_flags_weekend_bars_as_blocking():
    from quant.data.quality import validate_ohlcv

    # 2020-01-03 是周五，2020-01-04 是周六：周末 bar 说明交易日历错误。
    report = validate_ohlcv(_frame([("2020-01-02", 100), ("2020-01-03", 101), ("2020-01-04", 102)]))
    rules = {issue.rule for issue in report.issues}
    assert "non_trading_day_bars" in rules
    weekend = next(i for i in report.issues if i.rule == "non_trading_day_bars")
    assert weekend.severity == "blocking"
    assert "execution timing" in weekend.message


def test_halt_gap_is_reported_with_dates():
    from quant.data.quality import validate_ohlcv

    # 停牌/长缺口：1/2 → 2/3 间隔 32 天，必须显式报告而不是默默接起来。
    report = validate_ohlcv(_frame([("2020-01-02", 100), ("2020-02-03", 101)]))
    gaps = [i for i in report.issues if i.rule == "trading_day_gaps"]
    assert gaps and gaps[0].severity == "blocking"
    assert "2020-01-02" in (gaps[0].examples or [""])[0]


def test_delisted_member_absent_after_effective_to_but_window_still_runs():
    from quant.data.universe import Membership, validate_memberships

    members = [
        Membership(symbol="AAA", effective_from=date(2020, 1, 1), effective_to=date(2020, 6, 30)),
        Membership(symbol="BBB", effective_from=date(2020, 1, 1)),
    ]
    validate_memberships(members)
    # 退市当日仍在集合内（含端点），之后必须消失，不能沿用当前成分。
    assert [m.symbol for m in members if m.contains(date(2020, 6, 30))] == ["AAA", "BBB"]
    assert [m.symbol for m in members if m.contains(date(2020, 7, 1))] == ["BBB"]


def test_renamed_symbol_uses_map_file_span():
    import tempfile
    from pathlib import Path

    from quant.data.universe import Membership, write_lean_map_files

    members = [
        Membership(symbol="OLD", effective_from=date(2019, 1, 1), effective_to=date(2019, 12, 31)),
        Membership(symbol="NEW", effective_from=date(2020, 1, 1)),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "map_files"
        write_lean_map_files(out, members)
        old = (out / "old.csv").read_text(encoding="utf-8")
        new = (out / "new.csv").read_text(encoding="utf-8")
    # 更名前后各写各的有效区间（LEAN map 文件用 YYYYMMDD），避免把新代码回填到更名前。
    assert "20190101" in old and "20191231" in old
    assert "20200101" in new


def test_fundamentals_never_use_future_share_counts():
    from quant.data.fundamentals import Fundamentals

    shares = pd.DataFrame(
        {
            "as_of": pd.to_datetime(["2020-01-01", "2021-01-01"]).date,
            "shares_outstanding": [1000.0, 900.0],
        }
    )
    fund = Fundamentals(
        symbol="AAA",
        source="yfinance",
        shares=shares,
        sector="Tech",
        industry=None,
        sic=None,
        classified_as_of=date(2020, 6, 1),
    )
    # 2020-03-01 只能看到 2020-01-01 的股本，不能看到 2021 年的。
    assert fund.shares_as_of(date(2020, 3, 1)) == 1000.0
    assert fund.shares_as_of(date(2019, 12, 31)) is None  # 无可用股本 → 不猜
    # 分类在 known 日期之前不可用，避免用未来分类回填历史。
    assert fund.classification_known_on(date(2020, 5, 31)) is False
    assert fund.classification_known_on(date(2020, 6, 1)) is True


def test_unknown_universe_validity_is_marked_not_assumed():
    from quant.data.universe import Membership
    from quant.data.validity import (
        STATUS_POINT_IN_TIME,
        STATUS_SNAPSHOT,
        classify_universe_validity,
    )

    point_in_time = classify_universe_validity(
        [Membership(symbol="AAA", effective_from=date(2020, 1, 1), effective_to=date(2020, 6, 30))],
        ["AAA"],
        source="point_in_time",
    )
    assert point_in_time["status"] == STATUS_POINT_IN_TIME
    assert point_in_time["known"] is True
    assert point_in_time["effective_from"] == "2020-01-01"
    assert point_in_time["effective_to"] == "2020-06-30"

    unknown = classify_universe_validity([], ["AAA", "BBB"], source="snapshot")
    assert unknown["status"] == STATUS_SNAPSHOT
    assert unknown["known"] is False
    assert "有效期" in unknown["note"]
    assert "回填" in unknown["note"]


def test_backtest_out_exposes_universe_validity(client, monkeypatch):
    from services.api.services.backtests import data_status

    monkeypatch.setattr(
        "services.api.services.backtests.data_status",
        lambda *_a, **_k: {
            "ready": True,
            "corporate_actions_verified": True,
            "manifest": {"sha256": "abc", "snapshot_key": "snap"},
            "symbols": ["SPY"],
        },
    )
    monkeypatch.setattr("services.api.services.backtests._quality_gate", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "services.api.services.snapshots.ensure_snapshot_row", lambda *_a, **_k: None
    )
    assert data_status is not None

    created = client.post("/api/v1/strategies", json={"name": "P32"}).json()
    res = client.post(
        "/api/v1/backtests",
        json={
            "strategy_version_id": created["latest_version"]["id"],
            "start_date": "2020-01-01",
            "end_date": "2020-06-30",
            "benchmark": "SPY",
            "initial_capital": 100000,
        },
    )
    assert res.status_code in (200, 201), res.text
    body = res.json()
    assert body["universe_validity"]["status"] in {"snapshot", "config", "point_in_time"}
    if body["universe_validity"]["status"] != "point_in_time":
        assert body["universe_validity"]["known"] is False
        assert body["universe_validity"]["note"]
    # 列表输出同样带有效期标记
    listed = client.get("/api/v1/backtests").json()["items"]
    assert listed and "universe_validity" in listed[0]


@pytest.mark.parametrize("symbol", ["SPY"])
def test_membership_valid_on_filters_by_day(symbol):
    from quant.data.universe import Membership
    from quant.data.validity import membership_valid_on

    members = [
        Membership(symbol=symbol, effective_from=date(2020, 1, 1), effective_to=date(2020, 3, 31))
    ]
    assert membership_valid_on(members, date(2020, 2, 1)) == [symbol]
    assert membership_valid_on(members, date(2020, 4, 1)) == []
