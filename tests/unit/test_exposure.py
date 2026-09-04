from __future__ import annotations

from datetime import datetime, timezone

import pytest

from quant.metrics.performance import MetricParseError, summarize_exposure


def test_summarize_exposure_means():
    ts = datetime(2020, 1, 2, tzinfo=timezone.utc)
    series = [
        {"name": "exposure_long", "ts": ts, "value": 1.0},
        {"name": "exposure_long", "ts": ts, "value": 0.5},
        {"name": "exposure_short", "ts": ts, "value": 0.0},
        {"name": "exposure_short", "ts": ts, "value": 0.2},
        {"name": "turnover", "ts": ts, "value": 0.1},
        {"name": "turnover", "ts": ts, "value": 0.3},
    ]
    out = summarize_exposure(series)
    assert out["net_exposure"] == pytest.approx(0.65)
    assert out["gross_exposure"] == pytest.approx(0.85)
    assert out["turnover"] == pytest.approx(0.2)


def test_summarize_exposure_missing_is_none_not_zero():
    out = summarize_exposure([])
    assert out == {"turnover": None, "gross_exposure": None, "net_exposure": None}


def test_summarize_exposure_rejects_length_mismatch():
    ts = datetime(2020, 1, 2, tzinfo=timezone.utc)
    with pytest.raises(MetricParseError, match="长度不一致"):
        summarize_exposure(
            [
                {"name": "exposure_long", "ts": ts, "value": 1.0},
                {"name": "exposure_short", "ts": ts, "value": 0.0},
                {"name": "exposure_short", "ts": ts, "value": 0.1},
            ]
        )
