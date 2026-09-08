"""Paper execution ledger (E6-1).

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "paper_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("strategy_id", sa.Uuid(), nullable=False),
        sa.Column("initial_capital", sa.Float(), nullable=False),
        sa.Column("cash", sa.Float(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("strategy_id"),
    )
    op.create_index("ix_paper_accounts_strategy_id", "paper_accounts", ["strategy_id"])

    op.create_table(
        "paper_orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("strategy_id", sa.Uuid(), nullable=False),
        sa.Column("strategy_version_id", sa.Uuid(), nullable=True),
        sa.Column("client_order_id", sa.String(length=128), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=16), nullable=False),
        sa.Column("requested_quantity", sa.Float(), nullable=False),
        sa.Column("filled_quantity", sa.Float(), nullable=False),
        sa.Column("simulation_price", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("risk_reason", sa.String(length=255), nullable=True),
        sa.Column("risk_details", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["strategy_version_id"], ["strategy_versions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("strategy_id", "client_order_id", name="uq_paper_order_client_key"),
    )
    op.create_index("ix_paper_orders_strategy_id", "paper_orders", ["strategy_id"])
    op.create_index("ix_paper_orders_strategy_version_id", "paper_orders", ["strategy_version_id"])
    op.create_index("ix_paper_orders_symbol", "paper_orders", ["symbol"])

    op.create_table(
        "paper_fills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("strategy_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=16), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("fee", sa.Float(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["order_id"], ["paper_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_paper_fills_order_id", "paper_fills", ["order_id"])
    op.create_index("ix_paper_fills_strategy_id", "paper_fills", ["strategy_id"])
    op.create_index("ix_paper_fills_symbol", "paper_fills", ["symbol"])

    op.create_table(
        "paper_positions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("strategy_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("average_price", sa.Float(), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=False),
        sa.Column("mark_price", sa.Float(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("strategy_id", "symbol", name="uq_paper_position_symbol"),
    )
    op.create_index("ix_paper_positions_strategy_id", "paper_positions", ["strategy_id"])
    op.create_index("ix_paper_positions_symbol", "paper_positions", ["symbol"])

    op.create_table(
        "paper_reconciliations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("strategy_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expected_positions", sa.JSON(), nullable=False),
        sa.Column("actual_positions", sa.JSON(), nullable=False),
        sa.Column("differences", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_paper_reconciliations_strategy_id", "paper_reconciliations", ["strategy_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_paper_reconciliations_strategy_id", table_name="paper_reconciliations")
    op.drop_table("paper_reconciliations")
    op.drop_index("ix_paper_positions_symbol", table_name="paper_positions")
    op.drop_index("ix_paper_positions_strategy_id", table_name="paper_positions")
    op.drop_table("paper_positions")
    op.drop_index("ix_paper_fills_symbol", table_name="paper_fills")
    op.drop_index("ix_paper_fills_strategy_id", table_name="paper_fills")
    op.drop_index("ix_paper_fills_order_id", table_name="paper_fills")
    op.drop_table("paper_fills")
    op.drop_index("ix_paper_orders_symbol", table_name="paper_orders")
    op.drop_index("ix_paper_orders_strategy_version_id", table_name="paper_orders")
    op.drop_index("ix_paper_orders_strategy_id", table_name="paper_orders")
    op.drop_table("paper_orders")
    op.drop_index("ix_paper_accounts_strategy_id", table_name="paper_accounts")
    op.drop_table("paper_accounts")
