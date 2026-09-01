from __future__ import annotations

import json
from pathlib import Path

from quant.engine.result_parser import (
    find_result_json,
    parse_duration_days,
    parse_lean_result,
    rebase_benchmark,
)


def test_parse_closed_trades_round_trips(tmp_path: Path):
    payload = {
        "statistics": {
            "Net Profit": "1%",
            "Compounding Annual Return": "1%",
            "Drawdown": "2%",
            "Sharpe Ratio": "0.5",
            "Total Fees": "$2.00",
        },
        "charts": {
            "Strategy Equity": {
                "series": {
                    "Equity": {
                        "values": [
                            {"x": 1577836800, "y": 100000},
                            {"x": 1577923200, "y": 101000},
                            {"x": 1578009600, "y": 100500},
                        ]
                    }
                }
            },
            "Benchmark": {
                "series": {
                    "Benchmark": {
                        "values": [
                            {"x": 1577836800, "y": 320},
                            {"x": 1577923200, "y": 322},
                            {"x": 1578009600, "y": 321},
                        ]
                    }
                }
            },
        },
        "TotalPerformance": {
            "ClosedTrades": [
                {
                    "Symbol": {"value": "SPY"},
                    "EntryTime": 1577836800,
                    "EntryPrice": 320.0,
                    "ExitPrice": 330.0,
                    "Quantity": 10,
                    "ProfitLoss": 100.0,
                    "Duration": "5.00:00:00",
                    "TotalFees": 1.0,
                    "Direction": 0,
                }
            ]
        },
        "orders": {
            "1": {"symbol": {"value": "SPY"}, "quantity": 10, "price": 320.0, "time": 1577836800}
        },
    }
    path = tmp_path / "Spy200DmaAlgorithm.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    parsed = parse_lean_result(path)
    assert len(parsed["trades"]) == 1
    trade = parsed["trades"][0]
    assert trade["pnl"] == 100.0
    assert trade["exit_price"] == 330.0
    assert trade["holding_period"] == 5.0
    assert trade["direction"] == "LONG"
    assert parsed["metrics"]["extras"]["closed_trade_count"] == 1
    assert parsed["metrics"]["extras"]["benchmark_rebased"] is True


def test_find_result_json_prefers_algorithm_class(tmp_path: Path):
    (tmp_path / "data-monitor-report-1.json").write_text("{}", encoding="utf-8")
    target = tmp_path / "Spy200DmaAlgorithm.json"
    target.write_text(
        json.dumps(
            {"statistics": {"Net Profit": "1%"}, "charts": {"Strategy Equity": {"series": {}}}}
        ),
        encoding="utf-8",
    )
    found = find_result_json(tmp_path, algorithm_class="Spy200DmaAlgorithm")
    assert found == target


def test_find_result_json_skips_monitor_reports(tmp_path: Path):
    (tmp_path / "data-monitor-report-9.json").write_text(
        json.dumps({"statistics": {}, "charts": {}}), encoding="utf-8"
    )
    real = tmp_path / "other.json"
    real.write_text(json.dumps({"statistics": {"x": 1}, "charts": {"a": {}}}), encoding="utf-8")
    assert find_result_json(tmp_path) == real


def test_parse_duration_days():
    assert parse_duration_days("81.23:00:00") == 81 + 23 / 24
    assert parse_duration_days("1.00:00:00") == 1.0
    assert parse_duration_days(None) is None


def test_rebase_benchmark_records_decision():
    equity = [
        {"strategy_value": 100_000, "benchmark_value": 300},
        {"strategy_value": 101_000, "benchmark_value": 310},
    ]
    info = rebase_benchmark(equity, enabled=True)
    assert info["benchmark_rebased"] is True
    assert equity[0]["benchmark_value"] == 100_000
    disabled = [
        {"strategy_value": 100_000, "benchmark_value": 300},
        {"strategy_value": 101_000, "benchmark_value": 310},
    ]
    info2 = rebase_benchmark(disabled, enabled=False)
    assert info2["benchmark_rebased"] is False
    assert disabled[0]["benchmark_value"] == 300
