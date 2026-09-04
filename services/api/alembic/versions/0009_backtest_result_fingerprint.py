"""Phase 4 result cache fingerprint.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("backtests", sa.Column("result_fingerprint", sa.String(length=64), nullable=True))
    op.create_index(
        "ix_backtests_result_fingerprint",
        "backtests",
        ["result_fingerprint"],
    )


def downgrade() -> None:
    op.drop_index("ix_backtests_result_fingerprint", table_name="backtests")
    op.drop_column("backtests", "result_fingerprint")
