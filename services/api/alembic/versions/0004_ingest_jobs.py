"""Async ingest jobs with progress.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ingest_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress_step", sa.String(length=255), nullable=True),
        sa.Column("symbols", sa.JSON(), nullable=False),
        sa.Column("start", sa.String(length=32), nullable=False, server_default="2010-01-01"),
        sa.Column("end", sa.String(length=32), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False, server_default="auto"),
        sa.Column("mode", sa.String(length=32), nullable=False, server_default="full"),
        sa.Column("reconcile_with", sa.String(length=64), nullable=True),
        sa.Column("convert_lean", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("current_symbol", sa.String(length=16), nullable=True),
        sa.Column("completed_symbols", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_symbols", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.JSON(), nullable=True),
        sa.Column("data_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["data_snapshot_id"], ["data_snapshots.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingest_jobs_status", "ingest_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_ingest_jobs_status", table_name="ingest_jobs")
    op.drop_table("ingest_jobs")
