"""Portfolio allocation and attribution ledger (E8-1).

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("base_currency", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("initial_capital", sa.Float(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "portfolio_allocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("strategy_id", sa.Uuid(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "portfolio_id", "strategy_id", "effective_from", name="uq_portfolio_allocation_period"
        ),
    )
    op.create_index(
        "ix_portfolio_allocations_portfolio_id", "portfolio_allocations", ["portfolio_id"]
    )
    op.create_index(
        "ix_portfolio_allocations_strategy_id", "portfolio_allocations", ["strategy_id"]
    )

    op.create_table(
        "portfolio_attributions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("portfolio_return", sa.Float(), nullable=False),
        sa.Column("benchmark_return", sa.Float(), nullable=False),
        sa.Column("allocation_effect", sa.Float(), nullable=False),
        sa.Column("selection_effect", sa.Float(), nullable=False),
        sa.Column("interaction_effect", sa.Float(), nullable=False),
        sa.Column("active_return", sa.Float(), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("portfolio_id", "as_of", name="uq_portfolio_attribution_period"),
    )
    op.create_index(
        "ix_portfolio_attributions_portfolio_id", "portfolio_attributions", ["portfolio_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_portfolio_attributions_portfolio_id", table_name="portfolio_attributions")
    op.drop_table("portfolio_attributions")
    op.drop_index("ix_portfolio_allocations_strategy_id", table_name="portfolio_allocations")
    op.drop_index("ix_portfolio_allocations_portfolio_id", table_name="portfolio_allocations")
    op.drop_table("portfolio_allocations")
    op.drop_table("portfolios")
