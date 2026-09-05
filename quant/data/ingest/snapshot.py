from __future__ import annotations

import shutil
from pathlib import Path


def _repo_data_root() -> Path:
    return Path(__file__).resolve().parents[3] / "data"


def _copy_tree(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


def _publish_latest(root: Path, snap_dir: Path) -> None:
    """Point compatibility paths at the new snapshot without deleting history."""
    mapping = {
        "market": snap_dir / "market",
        "lean": snap_dir / "lean",
        "corporate_actions": snap_dir / "corporate_actions",
        "fundamentals": snap_dir / "fundamentals",
        "manifest.json": snap_dir / "manifest.json",
    }
    for name, src in mapping.items():
        dest = root / name
        if not src.exists():
            continue
        if dest.is_symlink():
            dest.unlink()
            dest.symlink_to(src if src.is_dir() else src, target_is_directory=src.is_dir())
        elif dest.exists() and dest.is_dir() and src.is_dir():
            _copy_tree(src, dest)
        elif src.is_file():
            shutil.copy2(src, dest)
        else:
            dest.symlink_to(src, target_is_directory=src.is_dir())


def latest_snapshot_dir(data_root: Path) -> Path | None:
    snaps = data_root / "snapshots"
    if not snaps.exists():
        return None
    dirs = [p for p in snaps.iterdir() if p.is_dir()]
    if not dirs:
        return None
    return max(dirs, key=lambda p: p.stat().st_mtime)


def prune_unreferenced_snapshots(data_root: Path, referenced_keys: set[str]) -> list[str]:
    snaps = data_root / "snapshots"
    if not snaps.exists():
        return []
    removed: list[str] = []
    for path in snaps.iterdir():
        if path.is_dir() and path.name not in referenced_keys:
            shutil.rmtree(path)
            removed.append(path.name)
    return removed
