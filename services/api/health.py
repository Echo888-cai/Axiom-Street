from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import text

from quant.engine.lean import LeanQuantEngine
from services.api.db import engine
from services.api.settings import get_settings
from services.worker.health import read_worker_health


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


def docker_status() -> dict[str, Any]:
    """Docker is owned by the worker. Prefer its heartbeat; fall back to a local probe."""
    settings = get_settings()
    local = LeanQuantEngine(
        lean_image=settings.lean_image,
        data_root=Path(settings.data_root),
        jobs_root=Path(settings.jobs_root),
    ).health_check()
    reported = read_worker_health()
    if reported is not None:
        available = bool(reported.get("docker_available"))
        return {
            "ok": available,
            "image": reported.get("image") or local.get("image"),
            "source": "worker",
            "reported_at": reported.get("reported_at"),
            "note": None
            if available
            else "Worker 上报 Docker 不可用。请确认 Colima/Docker 已启动，然后重启 worker。",
        }
    available = bool(local.get("docker_available"))
    if available:
        return {
            "ok": True,
            "image": local.get("image"),
            "source": "api",
            "reported_at": None,
            "note": None,
        }
    return {
        "ok": False,
        "image": local.get("image"),
        "source": "api",
        "reported_at": None,
        "note": "Worker 尚未上报 Docker 状态。compose 下 API 看不到 docker.sock 是预期行为；回测由 worker 执行。",
    }


def collect_health() -> dict[str, Any]:
    settings = get_settings()
    checks = {
        "postgres": _postgres(),
        "redis": _redis(),
        "docker": docker_status(),
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
