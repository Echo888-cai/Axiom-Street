"""Phase 4 research notes.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("strategy_id", sa.Uuid(), nullable=False),
        sa.Column("strategy_version_id", sa.Uuid(), nullable=True),
        sa.Column("backtest_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=False, server_default=""),
        sa.Column("method", sa.Text(), nullable=False, server_default=""),
        sa.Column("conclusion", sa.Text(), nullable=False, server_default=""),
        sa.Column("failure_modes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["strategy_version_id"], ["strategy_versions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["backtest_id"], ["backtests.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_research_notes_strategy_id", "research_notes", ["strategy_id"])
    op.create_index(
        "ix_research_notes_strategy_version_id", "research_notes", ["strategy_version_id"]
    )
    op.create_index("ix_research_notes_backtest_id", "research_notes", ["backtest_id"])


def downgrade() -> None:
    op.drop_index("ix_research_notes_backtest_id", table_name="research_notes")
    op.drop_index("ix_research_notes_strategy_version_id", table_name="research_notes")
    op.drop_index("ix_research_notes_strategy_id", table_name="research_notes")
    op.drop_table("research_notes")
