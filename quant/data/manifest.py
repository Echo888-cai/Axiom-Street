from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def manifest_path(data_root: Path) -> Path:
    return Path(data_root) / "manifest.json"


def load_manifest(data_root: Path) -> dict[str, Any]:
    path = manifest_path(data_root)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(data_root: Path, payload: dict[str, Any]) -> Path:
    path = manifest_path(data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path
