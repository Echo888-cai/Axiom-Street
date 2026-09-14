"""Continuous paper sessions: clock, orders, signals, observations (P5).

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "paper_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("strategy_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("current_bar_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_processed_bar_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("limits", sa.JSON(), nullable=False),
        sa.Column("account", sa.JSON(), nullable=False),
        sa.Column("observation_days", sa.Integer(), nullable=False),
        sa.Column("kill_switch", sa.Boolean(), nullable=False),
        sa.Column("deviation", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["strategy_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_paper_sessions_strategy_id", "paper_sessions", ["strategy_id"])

    op.create_table(
        "paper_session_signals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("bar_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("signal", sa.String(length=16), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["session_id"], ["paper_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "bar_date", "symbol", name="uq_paper_signal_bar"),
    )
    op.create_index("ix_paper_session_signals_session_id", "paper_session_signals", ["session_id"])

    op.create_table(
        "paper_session_orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("fee_slippage", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["paper_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_paper_session_orders_session_id", "paper_session_orders", ["session_id"])

    op.create_table(
        "paper_day_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("signals", sa.JSON(), nullable=False),
        sa.Column("orders", sa.JSON(), nullable=False),
        sa.Column("fills", sa.JSON(), nullable=False),
        sa.Column("fee_slippage", sa.JSON(), nullable=False),
        sa.Column("deviation", sa.JSON(), nullable=False),
        sa.Column("notes", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["session_id"], ["paper_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "day", name="uq_paper_observation_day"),
    )
    op.create_index(
        "ix_paper_day_observations_session_id", "paper_day_observations", ["session_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_paper_day_observations_session_id", table_name="paper_day_observations")
    op.drop_table("paper_day_observations")
    op.drop_index("ix_paper_session_orders_session_id", table_name="paper_session_orders")
    op.drop_table("paper_session_orders")
    op.drop_index("ix_paper_session_signals_session_id", table_name="paper_session_signals")
    op.drop_table("paper_session_signals")
    op.drop_index("ix_paper_sessions_strategy_id", table_name="paper_sessions")
    op.drop_table("paper_sessions")
