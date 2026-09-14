"""Workspace identity and isolation (P6A).

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "workspace_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member_user"),
    )
    op.create_index("ix_workspace_members_workspace_id", "workspace_members", ["workspace_id"])
    op.create_index("ix_workspace_members_user_id", "workspace_members", ["user_id"])

    op.execute(
        "INSERT INTO workspaces (id, slug, name) VALUES "
        "('00000000-0000-0000-0000-000000000001', 'default', '个人工作区') "
        "ON CONFLICT (slug) DO NOTHING"
    )
    op.add_column(
        "strategies",
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("'00000000-0000-0000-0000-000000000001'"),
        ),
    )
    op.create_foreign_key(
        "fk_strategies_workspace_id", "strategies", "workspaces", ["workspace_id"], ["id"]
    )
    op.create_index("ix_strategies_workspace_id", "strategies", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_strategies_workspace_id", table_name="strategies")
    op.drop_constraint("fk_strategies_workspace_id", "strategies", type_="foreignkey")
    op.drop_column("strategies", "workspace_id")
    op.drop_index("ix_workspace_members_user_id", table_name="workspace_members")
    op.drop_index("ix_workspace_members_workspace_id", table_name="workspace_members")
    op.drop_table("workspace_members")
    op.drop_table("workspaces")
