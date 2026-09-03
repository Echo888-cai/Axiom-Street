"""Walk-forward run status + progress on validation_runs.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "validation_runs",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="COMPLETED"),
    )
    op.add_column(
        "validation_runs",
        sa.Column("progress_step", sa.String(length=128), nullable=True),
    )
    op.create_index("ix_validation_runs_status", "validation_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_validation_runs_status", table_name="validation_runs")
    op.drop_column("validation_runs", "progress_step")
    op.drop_column("validation_runs", "status")
