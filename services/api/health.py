from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import text

from quant.engine.lean import LeanQuantEngine
from services.api.db import engine
from services.api.settings import get_settings


def _postgres() -> dict[str, Any]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001 - health must never raise
        return {"ok": False, "error": str(exc)}


def _redis() -> dict[str, Any]:
    try:
        import redis

        client = redis.Redis.from_url(get_settings().redis_url, socket_connect_timeout=1)
        client.ping()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def _docker() -> dict[str, Any]:
    settings = get_settings()
    lean = LeanQuantEngine(
        lean_image=settings.lean_image,
        data_root=Path(settings.data_root),
        jobs_root=Path(settings.jobs_root),
    ).health_check()
    return {
        "ok": bool(lean.get("docker_available")),
        "image": lean.get("image"),
        "note": None
        if lean.get("docker_available")
        else "API 进程看不到 Docker 是 compose 下的预期行为；worker 负责跑 LEAN。",
    }


def collect_health() -> dict[str, Any]:
    settings = get_settings()
    checks = {
        "postgres": _postgres(),
        "redis": _redis(),
        "docker": _docker(),
    }
    if not checks["postgres"]["ok"]:
        overall = "down"
    elif not checks["redis"]["ok"]:
        overall = "degraded"
    else:
        overall = "ok"
    return {
        "status": overall,
        "service": "api",
        "version": settings.app_version,
        "checks": checks,
    }
