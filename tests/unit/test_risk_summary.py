import pytest

from quant.risk.summary import RiskPosition, summarize_risk


def test_summarize_risk_calculates_equity_and_gross_net_exposure() -> None:
    result = summarize_risk(
        strategy_status="PAPER",
        risk_config={"max_gross_leverage": 1.5},
        initial_capital=100_000.0,
        cash=70_000.0,
        positions=[
            RiskPosition(quantity=100.0, mark_price=200.0),
            RiskPosition(quantity=-50.0, mark_price=100.0),
        ],
        reconciliation_status="MATCHED",
    )

    assert result.risk_config_valid is True
    assert result.equity == pytest.approx(85_000.0)
    assert result.gross_exposure == pytest.approx(25_000 / 85_000)
    assert result.net_exposure == pytest.approx(15_000 / 85_000)
    assert result.blocking_reasons == ()


def test_summarize_risk_reports_missing_account_and_invalid_limits() -> None:
    result = summarize_risk(
        strategy_status="BACKTESTED",
        risk_config={"unknown_limit": 1},
        initial_capital=None,
        cash=None,
        positions=[],
        reconciliation_status=None,
    )

    assert result.account_available is False
    assert result.equity is None
    assert result.gross_exposure is None
    assert result.net_exposure is None
    assert set(result.blocking_reasons) == {
        "strategy_not_paper_ready",
        "risk_limits_invalid",
        "paper_account_missing",
        "paper_reconciliation_not_matched",
    }


def test_summarize_risk_rejects_non_positive_equity() -> None:
    with pytest.raises(ValueError, match="paper account equity must remain positive"):
        summarize_risk(
            strategy_status="PAPER",
            risk_config={},
            initial_capital=100_000.0,
            cash=-1.0,
            positions=[],
            reconciliation_status="MATCHED",
        )
