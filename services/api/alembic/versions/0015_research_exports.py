"""Research reports: evidence list, validation linkage, AI provenance, frozen exports (P2.4).

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "research_notes",
        sa.Column("validation_run_id", sa.Uuid(), nullable=True),
    )
    op.add_column("research_notes", sa.Column("evidence", sa.JSON(), default=dict))
    op.add_column("research_notes", sa.Column("drafted_by", sa.JSON(), default=dict))
    op.create_foreign_key(
        "fk_research_notes_validation_run_id",
        "research_notes",
        "validation_runs",
        ["validation_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_research_notes_validation_run_id", "research_notes", ["validation_run_id"])

    op.create_table(
        "research_exports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("note_id", sa.Uuid(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["note_id"], ["research_notes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_research_exports_note_id", "research_exports", ["note_id"])


def downgrade() -> None:
    op.drop_index("ix_research_exports_note_id", table_name="research_exports")
    op.drop_table("research_exports")
    op.drop_index("ix_research_notes_validation_run_id", table_name="research_notes")
    op.drop_constraint("fk_research_notes_validation_run_id", "research_notes", type_="foreignkey")
    op.drop_column("research_notes", "drafted_by")
    op.drop_column("research_notes", "evidence")
    op.drop_column("research_notes", "validation_run_id")
