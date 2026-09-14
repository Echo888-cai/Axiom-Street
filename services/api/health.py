from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

from quant.engine.lean import LeanQuantEngine
from quant.security.sandbox import docker_security_args
from services.api.db import engine
from services.api.settings import get_settings
from services.worker.health import WORKER_HEALTH_TTL_SECONDS, read_worker_health


def worker_health_status(reported: dict[str, Any] | None) -> dict[str, Any]:
    """Return a bounded, credential-free view of the worker heartbeat."""
    if reported is None:
        return {
            "ok": False,
            "reported_at": None,
            "age_seconds": None,
            "heartbeat_ttl_seconds": WORKER_HEALTH_TTL_SECONDS,
            "image": None,
            "docker_available": False,
            "note": "Worker 尚未上报心跳。",
        }
    raw_reported_at = reported.get("reported_at")
    try:
        parsed = datetime.fromisoformat(str(raw_reported_at).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - parsed).total_seconds()
    except (TypeError, ValueError):
        age = None
    docker_available = bool(reported.get("docker_available"))
    fresh = age is not None and 0 <= age <= WORKER_HEALTH_TTL_SECONDS
    if not docker_available:
        note = "Worker 上报 Docker 不可用。"
    elif age is None:
        note = "Worker 心跳时间无效。"
    elif not fresh:
        note = "Worker 心跳已过期。"
    else:
        note = None
    return {
        "ok": docker_available and fresh,
        "reported_at": raw_reported_at,
        "age_seconds": age,
        "heartbeat_ttl_seconds": WORKER_HEALTH_TTL_SECONDS,
        "image": reported.get("image"),
        "docker_available": docker_available,
        "note": note,
    }


def security_status() -> dict[str, Any]:
    """Expose the actual shared LEAN sandbox posture without secrets."""
    args = docker_security_args()
    user = args[args.index("--user") + 1]
    explicit_seccomp = next(
        (item.split("=", 1)[1] for item in args if item.startswith("seccomp=")),
        "default",
    )
    return {
        "ok": (
            args[args.index("--network") + 1] == "none"
            and "--read-only" in args
            and user.split(":", 1)[0] != "0"
            and args[args.index("--cap-drop") + 1] == "ALL"
            and "no-new-privileges=true" in args
            and explicit_seccomp == "default"
            and "--tmpfs" in args
        ),
        "network": args[args.index("--network") + 1],
        "rootfs_read_only": "--read-only" in args,
        "non_root": user.split(":", 1)[0] != "0",
        "capabilities_dropped": args[args.index("--cap-drop") + 1],
        "no_new_privileges": "no-new-privileges=true" in args,
        "seccomp": explicit_seccomp,
        "tmpfs": "/tmp" if "--tmpfs" in args else None,
        "container_user": user,
    }


def _postgres() -> dict[str, Any]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001 - health must never raise
        return {"ok": False, "error": str(exc)}


def _database_revision() -> dict[str, Any]:
    """Alembic head actually applied to this database. Never raises: unknown
    means the instance cannot prove its schema matches the code."""
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version")).first()
    except Exception:  # noqa: BLE001 - health must never raise
        return {"revision": None, "note": "迁移版本未知（未建 alembic_version 表或不可读）。"}
    if row is None or not row[0]:
        return {"revision": None, "note": "迁移版本表为空。"}
    return {"revision": str(row[0])}


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
        worker = worker_health_status(reported)
        available = worker["ok"]
        return {
            "ok": available,
            "image": reported.get("image") or local.get("image"),
            "source": "worker",
            "reported_at": reported.get("reported_at"),
            "note": worker["note"],
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
        "worker": worker_health_status(read_worker_health()),
        "security": security_status(),
    }
    if not checks["postgres"]["ok"]:
        overall = "down"
    elif any(not checks[name]["ok"] for name in ("redis", "worker", "security")):
        overall = "degraded"
    else:
        overall = "ok"
    return {
        "status": overall,
        "service": "api",
        "version": settings.app_version,
        # P1.1: build identity the instance was deployed from (empty in dev
        # checkouts) plus the migration revision actually applied to this
        # database. Informational only — never flips the status above.
        "build_sha": settings.build_sha or None,
        "database_revision": _database_revision().get("revision"),
        "checks": checks,
    }
