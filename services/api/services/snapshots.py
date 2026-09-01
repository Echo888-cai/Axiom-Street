from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from quant.data.ingest_spy import prune_unreferenced_snapshots
from quant.data.manifest import load_manifest
from services.api.models import Backtest, DataSnapshot


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def upsert_snapshot_from_ingest(db: Session, result: dict[str, Any]) -> DataSnapshot:
    manifest = result.get("manifest") or {}
    snapshot_key = str(result.get("snapshot_key") or manifest.get("snapshot_key") or "")
    digest = str(result.get("content_sha256") or manifest.get("sha256") or "")
    if not snapshot_key:
        snapshot_key = f"legacy-{digest[:12]}" if digest else "unknown"
    existing = db.scalars(
        select(DataSnapshot).where(DataSnapshot.snapshot_key == snapshot_key)
    ).first()
    if existing:
        return existing

    previous = db.scalars(
        select(DataSnapshot)
        .where(DataSnapshot.superseded_by.is_(None))
        .order_by(DataSnapshot.created_at.desc())
    ).first()

    row = DataSnapshot(
        snapshot_key=snapshot_key,
        symbols=manifest.get("symbol") or ["SPY"],
        resolution=str(manifest.get("resolution") or "daily"),
        provider=str(manifest.get("source") or "unknown"),
        date_range_start=_parse_ts(manifest.get("start")),
        date_range_end=_parse_ts(manifest.get("end")),
        row_count=int(manifest.get("rows") or 0),
        content_sha256=digest,
        corporate_actions_verified=bool(manifest.get("corporate_actions_verified")),
        quality_report=result.get("quality_report") or manifest.get("quality_report") or {},
        provider_capabilities=manifest.get("provider_capabilities") or {},
    )
    db.add(row)
    db.flush()
    if previous and previous.id != row.id:
        previous.superseded_by = row.id
    return row


def ensure_snapshot_row(db: Session, data_root: Path) -> DataSnapshot | None:
    manifest = load_manifest(data_root)
    if not manifest:
        return None
    digest = str(manifest.get("sha256") or "")
    snapshot_key = str(manifest.get("snapshot_key") or (f"legacy-{digest[:12]}" if digest else ""))
    if not snapshot_key:
        return None
    existing = db.scalars(
        select(DataSnapshot).where(DataSnapshot.snapshot_key == snapshot_key)
    ).first()
    if existing:
        return existing
    return upsert_snapshot_from_ingest(
        db,
        {
            "snapshot_key": snapshot_key,
            "content_sha256": digest,
            "manifest": manifest,
            "quality_report": manifest.get("quality_report") or {},
        },
    )


def referenced_snapshot_keys(db: Session) -> set[str]:
    keys: set[str] = set()
    for snap in db.scalars(select(DataSnapshot)).all():
        used = db.scalars(
            select(Backtest.id).where(Backtest.data_snapshot_id == snap.id).limit(1)
        ).first()
        if used:
            keys.add(snap.snapshot_key)
    return keys


def prune_disk_snapshots(db: Session, data_root: Path) -> list[str]:
    keep = referenced_snapshot_keys(db)
    latest = db.scalars(
        select(DataSnapshot)
        .where(DataSnapshot.superseded_by.is_(None))
        .order_by(DataSnapshot.created_at.desc())
    ).first()
    if latest:
        keep.add(latest.snapshot_key)
    return prune_unreferenced_snapshots(data_root, keep)


def get_snapshot(db: Session, snapshot_id: UUID) -> DataSnapshot | None:
    return db.get(DataSnapshot, snapshot_id)
