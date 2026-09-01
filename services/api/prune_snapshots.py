from __future__ import annotations

from pathlib import Path

from services.api.db import SessionLocal
from services.api.services.snapshots import prune_disk_snapshots
from services.api.settings import get_settings


def main() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        removed = prune_disk_snapshots(db, Path(settings.data_root))
    finally:
        db.close()
    print(f"removed {len(removed)} snapshots: {removed}")


if __name__ == "__main__":
    main()
