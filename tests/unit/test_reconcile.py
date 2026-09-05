"""Dual-source reconciliation: close suspects + fail-closed corporate actions."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from quant.data.ingest import ingest
from quant.data.providers import (
    fetch_polygon,
    provider_status,
    resolve_primary_provider,
    resolve_reconcile_with,
)
from quant.data.reconcile import CLOSE_BPS_THRESHOLD, reconcile_frames
from quant.data.types import YFINANCE_CAPABILITIES, DataQualityError, FetchResult


def _frame(closes: dict[str, float], *, dividend_day: str | None = None) -> pd.DataFrame:
    rows = []
    for day, close in closes.items():
        rows.append(
            {
                "timestamp": datetime.fromisoformat(day).replace(tzinfo=timezone.utc),
                "open": close,
                "high": close + 1,
                "low": close - 1,
                "close": close,
                "volume": 1000,
                "dividends": 0.5 if dividend_day == day else 0.0,
                "stock_splits": 0.0,
                "exchange_timezone": "America/New_York",
                "symbol": "SPY",
            }
        )
    return pd.DataFrame(rows)


def test_close_mismatch_above_threshold_is_suspect():
    primary = _frame({"2020-01-02": 100.0, "2020-01-03": 101.0})
    # 20 bps off on day 2
    secondary = _frame({"2020-01-02": 100.20, "2020-01-03": 101.0})
    report = reconcile_frames(
        primary, secondary, primary_source="polygon", secondary_source="yfinance"
    )
    assert report.compared_bars == 2
    assert report.suspect_bars == 1
    assert any(i.rule == "dual_source_close_mismatch" for i in report.issues)
    assert all(
        i.severity == "warning" for i in report.issues if i.rule == "dual_source_close_mismatch"
    )


def test_close_within_threshold_is_clean():
    primary = _frame({"2020-01-02": 100.0})
    # 5 bps < 10 bps threshold
    secondary = _frame({"2020-01-02": 100.05})
    report = reconcile_frames(
        primary, secondary, primary_source="polygon", secondary_source="yfinance"
    )
    assert report.suspect_bars == 0
    assert report.issues == []
    assert CLOSE_BPS_THRESHOLD == 10.0


def test_ingest_records_close_mismatch_warning(monkeypatch, tmp_path):
    from quant.data.ingest import data_status

    primary = _frame({"2020-01-02": 100.0, "2020-01-03": 101.0})
    secondary = _frame({"2020-01-02": 100.20, "2020-01-03": 101.0})

    def fake_fetch(symbol: str, *, provider: str = "auto", start: str = "2010-01-01", end=None):
        if provider == "polygon":
            return FetchResult(primary.copy(), "polygon", YFINANCE_CAPABILITIES)
        if provider == "yfinance":
            return FetchResult(secondary.copy(), "yfinance", YFINANCE_CAPABILITIES)
        raise AssertionError(f"unexpected provider {provider}")

    monkeypatch.setattr("quant.data.ingest.fetch_daily", fake_fetch)
    result = ingest(
        symbols=["SPY"],
        data_root=tmp_path,
        convert_lean=False,
        provider="polygon",
        reconcile_with="yfinance",
    )
    reports = result["reconcile_reports"]
    assert reports[0]["suspect_bars"] == 1
    issues = result["quality_report"]["issues"]
    assert any(i["rule"] == "dual_source_close_mismatch" for i in issues)
    status = data_status(tmp_path)
    assert status["reconcile_with"] == "yfinance"
    assert status["reconcile_reports"][0]["suspect_bars"] == 1


def test_dividend_mismatch_is_blocking():
    primary = _frame({"2020-01-02": 100.0, "2020-01-03": 101.0}, dividend_day="2020-01-02")
    secondary = _frame({"2020-01-02": 100.0, "2020-01-03": 101.0})
    report = reconcile_frames(
        primary, secondary, primary_source="polygon", secondary_source="yfinance"
    )
    assert report.has_blocking_issues
    assert any(i.rule == "dual_source_dividend_mismatch" for i in report.issues)


def test_polygon_without_key_fails_loud(monkeypatch):
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="POLYGON_API_KEY"):
        fetch_polygon("SPY", start="2020-01-01", end="2020-01-10")


def test_provider_status_marks_polygon_wired():
    status = provider_status()
    poly = status["optional_providers"]["polygon"]
    assert poly["wired"] is True
    assert "POLYGON_API_KEY" in poly["env"]


def test_auto_provider_uses_polygon_when_key_present(monkeypatch):
    monkeypatch.setenv("POLYGON_API_KEY", "test-key")
    assert resolve_primary_provider("auto") == "polygon"
    assert resolve_reconcile_with("polygon") == "yfinance"
    status = provider_status()
    assert status["primary"] == "polygon"
    assert status["reconcile_with"] == "yfinance"


def test_auto_provider_stays_yahoo_without_key(monkeypatch):
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    assert resolve_primary_provider("auto") == "auto"
    assert resolve_reconcile_with("auto") is None


def test_explicit_empty_reconcile_disables_default(monkeypatch):
    monkeypatch.setenv("POLYGON_API_KEY", "test-key")
    assert resolve_reconcile_with("polygon", "") is None


def test_empty_env_keeps_polygon_yfinance_default(monkeypatch):
    monkeypatch.setenv("POLYGON_API_KEY", "test-key")
    monkeypatch.setenv("STREET_RECONCILE_WITH", "")
    assert resolve_reconcile_with("polygon") == "yfinance"


def test_ingest_reconcile_blocks_on_corp_action_mismatch(monkeypatch, tmp_path):
    primary = _frame({"2020-01-02": 100.0, "2020-01-03": 100.5}, dividend_day="2020-01-02")
    secondary = _frame({"2020-01-02": 100.0, "2020-01-03": 100.5})

    def fake_fetch(symbol: str, *, provider: str = "auto", start: str = "2010-01-01", end=None):
        if provider == "polygon":
            return FetchResult(primary.copy(), "polygon", YFINANCE_CAPABILITIES)
        if provider == "yfinance":
            return FetchResult(secondary.copy(), "yfinance", YFINANCE_CAPABILITIES)
        raise AssertionError(f"unexpected provider {provider}")

    monkeypatch.setattr("quant.data.ingest.fetch_daily", fake_fetch)
    with pytest.raises(DataQualityError) as exc:
        ingest(
            symbols=["SPY"],
            data_root=tmp_path,
            convert_lean=False,
            provider="polygon",
            reconcile_with="yfinance",
        )
    assert exc.value.report["has_blocking_issues"] is True
