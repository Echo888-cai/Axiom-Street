"""Phase 1.5 trust tables: snapshots, trials, rolling windows.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("strategies", sa.Column("family_id", sa.Uuid(), nullable=True))
    op.create_index("ix_strategies_family_id", "strategies", ["family_id"])

    op.create_table(
        "data_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_key", sa.String(length=128), nullable=False),
        sa.Column("symbols", sa.JSON(), nullable=True),
        sa.Column("resolution", sa.String(length=32), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("date_range_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_range_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("corporate_actions_verified", sa.Boolean(), nullable=True),
        sa.Column("quality_report", sa.JSON(), nullable=True),
        sa.Column("provider_capabilities", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("superseded_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["superseded_by"], ["data_snapshots.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_key"),
    )
    op.create_index("ix_data_snapshots_content_sha256", "data_snapshots", ["content_sha256"])

    op.add_column("backtests", sa.Column("data_snapshot_id", sa.Uuid(), nullable=True))
    op.create_index("ix_backtests_data_snapshot_id", "backtests", ["data_snapshot_id"])
    op.create_foreign_key(
        "fk_backtests_data_snapshot_id",
        "backtests",
        "data_snapshots",
        ["data_snapshot_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "experiment_trials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("backtest_id", sa.Uuid(), nullable=True),
        sa.Column("data_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("strategy_id", sa.Uuid(), nullable=True),
        sa.Column("universe_key", sa.String(length=128), nullable=True),
        sa.Column("strategy_family", sa.Uuid(), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("parameter_hash", sa.String(length=64), nullable=True),
        sa.Column("observed_sharpe", sa.Float(), nullable=True),
        sa.Column("is_oos", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["backtest_id"], ["backtests.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["data_snapshot_id"], ["data_snapshots.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_experiment_trials_parameter_hash", "experiment_trials", ["parameter_hash"])
    op.create_index(
        "ix_experiment_trials_strategy_family", "experiment_trials", ["strategy_family"]
    )

    op.create_table(
        "backtest_rolling_windows",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("backtest_id", sa.Uuid(), nullable=False),
        sa.Column("window_key", sa.String(length=64), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sharpe", sa.Float(), nullable=True),
        sa.Column("var_95", sa.Float(), nullable=True),
        sa.Column("var_99", sa.Float(), nullable=True),
        sa.Column("probabilistic_sharpe", sa.Float(), nullable=True),
        sa.Column("extras", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["backtest_id"], ["backtests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_backtest_rolling_windows_backtest_id", "backtest_rolling_windows", ["backtest_id"]
    )

    op.create_table(
        "backtest_time_series",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("backtest_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["backtest_id"], ["backtests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_backtest_time_series_backtest_id", "backtest_time_series", ["backtest_id"])
    op.create_index("ix_backtest_time_series_name", "backtest_time_series", ["name"])


def downgrade() -> None:
    op.drop_index("ix_backtest_time_series_name", table_name="backtest_time_series")
    op.drop_index("ix_backtest_time_series_backtest_id", table_name="backtest_time_series")
    op.drop_table("backtest_time_series")
    op.drop_index("ix_backtest_rolling_windows_backtest_id", table_name="backtest_rolling_windows")
    op.drop_table("backtest_rolling_windows")
    op.drop_index("ix_experiment_trials_strategy_family", table_name="experiment_trials")
    op.drop_index("ix_experiment_trials_parameter_hash", table_name="experiment_trials")
    op.drop_table("experiment_trials")
    op.drop_constraint("fk_backtests_data_snapshot_id", "backtests", type_="foreignkey")
    op.drop_index("ix_backtests_data_snapshot_id", table_name="backtests")
    op.drop_column("backtests", "data_snapshot_id")
    op.drop_index("ix_data_snapshots_content_sha256", table_name="data_snapshots")
    op.drop_table("data_snapshots")
    op.drop_index("ix_strategies_family_id", table_name="strategies")
    op.drop_column("strategies", "family_id")
