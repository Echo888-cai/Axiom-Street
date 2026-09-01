from pathlib import Path


def test_alembic_baseline_creates_tables():
    text = Path("services/api/alembic/versions/0001_initial.py").read_text(encoding="utf-8")
    assert "def upgrade() -> None:" in text
    assert "pass" not in text.split("def upgrade")[1].split("def downgrade")[0]
    for table in (
        "users",
        "strategies",
        "strategy_versions",
        "backtests",
        "backtest_metrics",
        "backtest_equity",
        "backtest_trades",
        "backtest_monthly_returns",
        "audit_logs",
    ):
        assert f'"{table}"' in text
    assert "excess_return" in text
    assert "alpha_capm" in text
