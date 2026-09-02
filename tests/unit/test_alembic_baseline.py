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
    text2 = Path("services/api/alembic/versions/0002_phase15_trust.py").read_text(encoding="utf-8")
    assert "experiment_trials" in text2
    assert "data_snapshots" in text2
    assert "backtest_rolling_windows" in text2
    text3 = Path("services/api/alembic/versions/0003_universes.py").read_text(encoding="utf-8")
    assert "universes" in text3
    assert "universe_members" in text3
    assert "effective_from" in text3
    assert "effective_to" in text3
    assert "universe_snapshot" in text3
    text4 = Path("services/api/alembic/versions/0004_ingest_jobs.py").read_text(encoding="utf-8")
    assert "ingest_jobs" in text4
    assert "completed_symbols" in text4
    text5 = Path("services/api/alembic/versions/0005_universe_rules.py").read_text(encoding="utf-8")
    assert "rules" in text5
