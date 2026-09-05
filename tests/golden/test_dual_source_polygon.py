"""Live dual-source golden: Polygon vs yfinance when POLYGON_API_KEY is set.

Skipped without a key so nightly/CI stay green. This is the Phase 2
acceptance that a real vendor pair produces a reconcile report with
overlapping bars (and surfaces suspect closes when they exist).
"""

from __future__ import annotations

import pytest

from quant.data.ingest import ingest
from quant.data.providers import fetch_polygon, fetch_yfinance, polygon_configured
from quant.data.reconcile import reconcile_frames

WINDOW_START = "2020-02-03"
WINDOW_END = "2020-04-30"


@pytest.mark.golden
def test_polygon_yfinance_dual_source_golden(tmp_path):
    if not polygon_configured():
        pytest.skip("POLYGON_API_KEY not set — dual-source golden needs a live Polygon key")

    primary = fetch_polygon("SPY", start=WINDOW_START, end=WINDOW_END)
    secondary = fetch_yfinance("SPY", start=WINDOW_START, end=WINDOW_END)
    report = reconcile_frames(
        primary,
        secondary,
        primary_source="polygon",
        secondary_source="yfinance",
    )
    assert report.compared_bars >= 20, "Polygon and yfinance must overlap on the COVID window"
    assert report.primary_source == "polygon"
    assert report.secondary_source == "yfinance"
    if report.suspect_bars:
        mismatch = [i for i in report.issues if i.rule == "dual_source_close_mismatch"]
        assert mismatch, "suspect bars must name the close-mismatch rule"
        assert mismatch[0].examples, "reconcile report must cite at least one historical bar"

    result = ingest(
        symbols=["SPY"],
        data_root=tmp_path,
        start=WINDOW_START,
        end=WINDOW_END,
        provider="polygon",
        reconcile_with="yfinance",
        convert_lean=False,
    )
    reports = result["reconcile_reports"]
    assert reports, "ingest must persist the dual-source report"
    assert reports[0]["compared_bars"] >= 20
    assert reports[0]["primary_source"] == "polygon"
    assert result["manifest"]["reconcile_with"] == "yfinance"
    assert result["manifest"]["source"] == "polygon"
    # Corporate-action disagreements are blocking; a completed ingest means none fired.
    assert reports[0]["has_blocking_issues"] is False


@pytest.mark.golden
def test_polygon_fetch_fails_loud_without_key(monkeypatch):
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="POLYGON_API_KEY"):
        fetch_polygon("SPY", start="2020-01-01", end="2020-01-10")
