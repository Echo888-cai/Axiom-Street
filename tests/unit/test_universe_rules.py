from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd
import pytest

from quant.data.universe_rules import (
    evaluate_symbol,
    parse_rules,
    passing_dates,
)


def _frame(closes: list[tuple[int, float, float]]) -> pd.DataFrame:
    rows = []
    for day, close, volume in closes:
        rows.append(
            {
                "timestamp": datetime(2020, 1, day, tzinfo=timezone.utc),
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": volume,
                "dividends": 0.0,
                "stock_splits": 0.0,
                "symbol": "XYZ",
            }
        )
    return pd.DataFrame(rows)


def test_parse_rules_requires_a_threshold():
    with pytest.raises(ValueError, match="至少指定"):
        parse_rules({"lookback_days": 5})


def test_parse_rules_rejects_unknown_keys():
    with pytest.raises(ValueError, match="未知"):
        parse_rules({"min_price": 5, "sector": "tech"})


def test_warmup_bars_never_pass_liquidity_screen():
    rules = parse_rules({"min_adv_usd": 1000, "lookback_days": 2})
    frame = _frame([(2, 10.0, 100.0), (3, 10.0, 100.0), (6, 10.0, 100.0)])
    # dollar volume = 1000 each day; ADV ready from the second bar.
    assert passing_dates(frame, rules) == [date(2020, 1, 3), date(2020, 1, 6)]


def test_fail_day_splits_membership():
    rules = parse_rules({"min_price": 9, "lookback_days": 1})
    frame = _frame(
        [
            (2, 10.0, 1.0),
            (3, 10.0, 1.0),
            (6, 8.0, 1.0),
            (7, 10.0, 1.0),
        ]
    )
    members = evaluate_symbol(frame, "XYZ", rules)
    assert [m.to_dict() for m in members] == [
        {"symbol": "XYZ", "effective_from": "2020-01-02", "effective_to": "2020-01-03"},
        {"symbol": "XYZ", "effective_from": "2020-01-07", "effective_to": None},
    ]


def test_open_ended_when_last_bar_still_passes():
    rules = parse_rules({"min_price": 5, "lookback_days": 1})
    frame = _frame([(2, 10.0, 1.0), (3, 10.0, 1.0)])
    members = evaluate_symbol(frame, "XYZ", rules)
    assert len(members) == 1
    assert members[0].effective_from == date(2020, 1, 2)
    assert members[0].effective_to is None
