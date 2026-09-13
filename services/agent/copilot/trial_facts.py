"""Aggregate-only trial ledger projection for research context.

The database reduces the ledger before any rows cross into the Agent domain.
Memory and result size scale with snapshots, not the number of experiments.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from services.api.models import DataSnapshot, ExperimentTrial


def trial_facts(db: Session, family_id: UUID) -> list[dict[str, Any]]:
    """Count family trials and repeated non-empty hashes per snapshot.

    NULL/empty hashes are not duplicates; unknown snapshots remain explicit.
    Snapshot joins happen after aggregation so they cannot inflate trial counts.
    """
    non_empty_hash = func.nullif(ExperimentTrial.parameter_hash, "")
    counts = (
        select(
            ExperimentTrial.data_snapshot_id,
            func.count().label("count"),
            (func.count(non_empty_hash) - func.count(func.distinct(non_empty_hash))).label(
                "duplicate_parameter_hashes"
            ),
        )
        .where(ExperimentTrial.strategy_family == family_id)
        .group_by(ExperimentTrial.data_snapshot_id)
        .subquery()
    )
    successor = aliased(DataSnapshot)
    rows = db.execute(
        select(
            counts.c.data_snapshot_id,
            DataSnapshot.snapshot_key,
            successor.snapshot_key.label("superseded_by_key"),
            counts.c.count,
            counts.c.duplicate_parameter_hashes,
        )
        .select_from(counts)
        .outerjoin(DataSnapshot, DataSnapshot.id == counts.c.data_snapshot_id)
        .outerjoin(successor, successor.id == DataSnapshot.superseded_by)
        .order_by(counts.c.count.desc(), func.coalesce(DataSnapshot.snapshot_key, ""))
    ).mappings()
    return [dict(row) for row in rows]
