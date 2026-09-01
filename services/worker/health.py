from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import redis

from quant.engine.lean import LeanQuantEngine
from services.api.settings import get_settings

WORKER_HEALTH_KEY = "axiom:worker:health"
WORKER_HEALTH_TTL_SECONDS = 90


def _client() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def publish_worker_health() -> dict[str, Any]:
    """Probe Docker from the worker (the process that has docker.sock) and cache it."""
    settings = get_settings()
    lean = LeanQuantEngine(
        lean_image=settings.lean_image,
        data_root=Path(settings.data_root),
        jobs_root=Path(settings.jobs_root),
    ).health_check()
    payload: dict[str, Any] = {
        "docker_available": bool(lean.get("docker_available")),
        "image": lean.get("image"),
        "engine": lean.get("engine") or "lean",
        "reported_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        _client().setex(WORKER_HEALTH_KEY, WORKER_HEALTH_TTL_SECONDS, json.dumps(payload))
    except redis.RedisError:
        payload["redis_error"] = True
    return payload


def read_worker_health() -> dict[str, Any] | None:
    try:
        raw = _client().get(WORKER_HEALTH_KEY)
    except redis.RedisError:
        return None
    if not isinstance(raw, str):
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
