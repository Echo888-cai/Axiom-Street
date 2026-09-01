import json
from pathlib import Path

from quant.engine.result_parser import parse_lean_result


def test_parse_lean_result_fixture(tmp_path: Path):
    payload = {
        "statistics": {
            "Net Profit": "12.5%",
            "Compounding Annual Return": "8.1%",
            "Drawdown": "15%",
            "Sharpe Ratio": "1.23",
            "Total Orders": "10",
            "Win Rate": "55%",
            "Total Fees": "$12.00",
        },
        "charts": {
            "Strategy Equity": {
                "series": {
                    "Equity": {
                        "values": [
                            {"x": 1577836800, "y": 100000},
                            {"x": 1577923200, "y": 101000},
                            {"x": 1578009600, "y": 99000},
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
                            {"x": 1578009600, "y": 318},
                        ]
                    }
                }
            },
            "Drawdown": {
                "series": {
                    "Equity Drawdown": {
                        "values": [
                            {"x": 1577836800, "y": 0},
                            {"x": 1577923200, "y": 0},
                            {"x": 1578009600, "y": -0.02},
                        ]
                    }
                }
            },
        },
        "orders": {
            "1": {
                "symbol": {"value": "SPY"},
                "direction": "buy",
                "quantity": 100,
                "price": 320.1,
                "time": 1577923200,
            }
        },
    }
    path = tmp_path / "result.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    parsed = parse_lean_result(path)
    assert len(parsed["equity"]) == 3
    assert parsed["metrics"]["trade_count"] == 1
    assert parsed["metrics"]["commission"] == 12.0
    assert parsed["metrics"]["sharpe"] != 1.23
    assert parsed["metrics"]["max_drawdown"] > -0.15
    assert parsed["metrics"]["extras"]["lean_statistics"]["Sharpe Ratio"] == "1.23"
    assert len(parsed["trades"]) == 1
