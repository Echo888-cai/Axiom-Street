"""Point-in-time universes.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "universes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="STATIC"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "universe_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("universe_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["universe_id"], ["universes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "universe_id", "symbol", "effective_from", name="uq_universe_member_span"
        ),
    )
    op.create_index("ix_universe_members_universe_id", "universe_members", ["universe_id"])
    op.create_index("ix_universe_members_symbol", "universe_members", ["symbol"])

    op.add_column("backtests", sa.Column("universe_id", sa.Uuid(), nullable=True))
    op.add_column("backtests", sa.Column("universe_snapshot", sa.JSON(), nullable=True))
    op.create_index("ix_backtests_universe_id", "backtests", ["universe_id"])
    op.create_foreign_key(
        "fk_backtests_universe_id",
        "backtests",
        "universes",
        ["universe_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_backtests_universe_id", "backtests", type_="foreignkey")
    op.drop_index("ix_backtests_universe_id", table_name="backtests")
    op.drop_column("backtests", "universe_snapshot")
    op.drop_column("backtests", "universe_id")
    op.drop_index("ix_universe_members_symbol", table_name="universe_members")
    op.drop_index("ix_universe_members_universe_id", table_name="universe_members")
    op.drop_table("universe_members")
    op.drop_table("universes")
