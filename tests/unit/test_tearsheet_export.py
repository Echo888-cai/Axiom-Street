from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from services.api.services import tearsheet_export


def test_render_pdf_handles_cjk_title_and_equity_path(monkeypatch):
    backtest = SimpleNamespace(
        start_date="2018-01-01",
        end_date="2020-12-31",
        initial_capital=100_000.0,
        benchmark="SPY",
        data_version="snap",
        engine_version="quantconnect/lean:16355",
    )
    metrics = SimpleNamespace(
        total_return=0.1,
        cagr=0.05,
        sharpe=1.2,
        deflated_sharpe=0.8,
        probabilistic_sharpe=0.9,
        dsr_n_trials=3,
        max_drawdown=-0.2,
        volatility=0.15,
        excess_return=0.02,
        alpha_capm=0.01,
        beta=0.9,
        information_ratio=0.4,
        sortino=1.1,
        calmar=0.3,
        var_95=-0.02,
        cvar_95=-0.03,
        tail_ratio=1.2,
        gross_exposure=1.0,
        net_exposure=0.5,
        turnover=0.2,
        trade_count=10,
        commission=12.0,
        final_equity=110_000.0,
        extras={"benchmark_rebased": True},
    )
    equity = [SimpleNamespace(strategy_value=100_000.0 + i * 25.0) for i in range(30)]

    monkeypatch.setattr(
        tearsheet_export,
        "_load",
        lambda _db, _bid: (backtest, metrics, equity, "SPY 200日均线"),
    )

    payload = tearsheet_export.render_pdf(object(), uuid4())
    assert payload.startswith(b"%PDF")
    assert len(payload) > 1000
