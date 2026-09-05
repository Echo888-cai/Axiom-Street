#!/usr/bin/env python3
"""
Prune old job directories, keeping only golden + recent N runs.
"""

import shutil
from pathlib import Path


def prune_jobs(jobs_dir: Path, keep_recent: int = 20, dry_run: bool = False) -> tuple[int, int]:
    """
    Prune job directories.

    Keeps:
    - jobs/golden/
    - The most recent `keep_recent` job directories (by mtime)

    Returns:
        (deleted_count, kept_count)
    """
    if not jobs_dir.exists():
        return 0, 0

    all_dirs = [d for d in jobs_dir.iterdir() if d.is_dir()]

    # Separate golden
    golden_dir = jobs_dir / "golden"
    other_dirs = [d for d in all_dirs if d != golden_dir]

    # Sort by mtime (newest first)
    other_dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)

    to_keep = set()
    if golden_dir.exists():
        to_keep.add(golden_dir)
    to_keep.update(other_dirs[:keep_recent])

    to_delete = [d for d in other_dirs if d not in to_keep]

    deleted = 0
    for d in to_delete:
        if dry_run:
            print(f"[dry-run] Would delete: {d.name}")
        else:
            print(f"Deleting: {d.name}")
            shutil.rmtree(d)
        deleted += 1

    kept = len(to_keep)
    print(f"Kept: {kept} (golden + {min(keep_recent, len(other_dirs))} recent), Deleted: {deleted}")
    return deleted, kept


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Prune old job directories")
    parser.add_argument("--jobs-dir", default="jobs", help="Path to jobs directory")
    parser.add_argument("--keep-recent", type=int, default=20, help="Number of recent jobs to keep")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be deleted without deleting"
    )
    args = parser.parse_args()

    jobs_dir = Path(args.jobs_dir)
    if not jobs_dir.is_absolute():
        jobs_dir = Path.cwd() / jobs_dir

    prune_jobs(jobs_dir, args.keep_recent, args.dry_run)


if __name__ == "__main__":
    main()
