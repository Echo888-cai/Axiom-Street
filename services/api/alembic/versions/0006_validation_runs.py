"""Phase 3 validation_runs + DSR columns on backtest_metrics.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("backtest_metrics", sa.Column("deflated_sharpe", sa.Float(), nullable=True))
    op.add_column("backtest_metrics", sa.Column("probabilistic_sharpe", sa.Float(), nullable=True))
    op.add_column("backtest_metrics", sa.Column("dsr_n_trials", sa.Integer(), nullable=True))
    op.add_column("backtest_metrics", sa.Column("dsr_sr_star", sa.Float(), nullable=True))
    op.create_table(
        "validation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("strategy_id", sa.Uuid(), nullable=True),
        sa.Column("strategy_version_id", sa.Uuid(), nullable=True),
        sa.Column("backtest_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("error", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["strategy_version_id"], ["strategy_versions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["backtest_id"], ["backtests.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_validation_runs_strategy_id", "validation_runs", ["strategy_id"])
    op.create_index("ix_validation_runs_backtest_id", "validation_runs", ["backtest_id"])
    op.create_index(
        "ix_validation_runs_strategy_version_id", "validation_runs", ["strategy_version_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_validation_runs_strategy_version_id", table_name="validation_runs")
    op.drop_index("ix_validation_runs_backtest_id", table_name="validation_runs")
    op.drop_index("ix_validation_runs_strategy_id", table_name="validation_runs")
    op.drop_table("validation_runs")
    op.drop_column("backtest_metrics", "dsr_sr_star")
    op.drop_column("backtest_metrics", "dsr_n_trials")
    op.drop_column("backtest_metrics", "probabilistic_sharpe")
    op.drop_column("backtest_metrics", "deflated_sharpe")
