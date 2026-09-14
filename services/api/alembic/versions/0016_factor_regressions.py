"""Factor regression ledger (P3.4).

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "factor_regressions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=True),
        sa.Column("window_end", sa.Date(), nullable=True),
        sa.Column("model", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("frequency", sa.String(length=32), nullable=False),
        sa.Column("alpha", sa.Float(), nullable=False),
        sa.Column("r2", sa.Float(), nullable=False),
        sa.Column("n_obs", sa.Integer(), nullable=False),
        sa.Column("exposures", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_factor_regressions_portfolio_id", "factor_regressions", ["portfolio_id"])


def downgrade() -> None:
    op.drop_index("ix_factor_regressions_portfolio_id", table_name="factor_regressions")
    op.drop_table("factor_regressions")
