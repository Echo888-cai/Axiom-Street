from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.api import health


def test_worker_health_marks_missing_and_stale_heartbeats_unhealthy():
    missing = health.worker_health_status(None)
    assert missing["ok"] is False
    assert missing["reported_at"] is None

    stale_at = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    stale = health.worker_health_status(
        {
            "docker_available": True,
            "image": "lean:test",
            "reported_at": stale_at,
        }
    )
    assert stale["ok"] is False
    assert stale["age_seconds"] >= 120
    assert stale["image"] == "lean:test"


def test_collect_health_is_down_for_postgres_and_degraded_for_worker(monkeypatch):
    monkeypatch.setattr(health, "_postgres", lambda: {"ok": False, "error": "db"})
    monkeypatch.setattr(health, "_redis", lambda: {"ok": True})
    monkeypatch.setattr(
        health,
        "docker_status",
        lambda: {"ok": True, "source": "worker", "reported_at": None},
    )
    monkeypatch.setattr(health, "read_worker_health", lambda: None)
    assert health.collect_health()["status"] == "down"

    monkeypatch.setattr(health, "_postgres", lambda: {"ok": True})
    body = health.collect_health()
    assert body["status"] == "degraded"
    assert body["checks"]["worker"]["ok"] is False


def test_security_health_reports_enforced_sandbox_flags():
    security = health.security_status()
    assert security["ok"] is True
    assert security["network"] == "none"
    assert security["rootfs_read_only"] is True
    assert security["non_root"] is True
    assert security["seccomp"] == "default"


def test_stale_worker_cannot_report_usable_docker(monkeypatch):
    stale = {
        "reported_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
        "docker_available": True,
        "image": "lean:test",
    }
    monkeypatch.setattr(health, "read_worker_health", lambda: stale)
    body = health.docker_status()
    assert body["source"] == "worker"
    assert body["ok"] is False
    assert body["note"]


def test_future_worker_timestamp_is_not_a_fresh_heartbeat():
    future = {
        "reported_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "docker_available": True,
        "image": "lean:test",
    }
    assert health.worker_health_status(future)["ok"] is False


def test_health_reports_build_identity_without_flipping_status(monkeypatch):
    from services.api.settings import get_settings

    monkeypatch.setattr(health, "_postgres", lambda: {"ok": True})
    monkeypatch.setattr(health, "_redis", lambda: {"ok": True})
    monkeypatch.setattr(
        health,
        "docker_status",
        lambda: {"ok": True, "source": "worker", "reported_at": None},
    )
    monkeypatch.setattr(health, "read_worker_health", lambda: {"reported_at": None, "ok": True})
    monkeypatch.setattr(health, "_database_revision", lambda: {"revision": "0009_x"})
    get_settings.cache_clear()
    monkeypatch.setenv("STREET_BUILD_SHA", "abc123")
    get_settings.cache_clear()
    try:
        body = health.collect_health()
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
    assert body["build_sha"] == "abc123"
    assert body["database_revision"] == "0009_x"
    assert body["status"] in {"ok", "degraded"}


def test_database_revision_is_none_when_unmigrated(monkeypatch):
    import sqlalchemy
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from services.api import db as db_module

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(health, "engine", engine)
    assert health._database_revision() == {
        "revision": None,
        "note": "迁移版本未知（未建 alembic_version 表或不可读）。",
    }
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        )
        conn.execute(sqlalchemy.text("INSERT INTO alembic_version VALUES ('0012_y')"))
    assert health._database_revision() == {"revision": "0012_y"}


def test_health_endpoint_exposes_build_and_revision(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["version"] == "0.1.0"
    assert "build_sha" in body
    assert "database_revision" in body


def test_beat_schedule_tasks_are_registered():
    """Every periodic beat delivery must resolve to a registered task.

    Regression pin: worker.publish_health was scheduled but never
    registered, so heartbeats never published and every delivery raised
    KeyError on the worker."""
    from services.worker import tasks as _tasks  # noqa: F401  (import registers tasks)
    from services.worker.celery_app import _beat_schedule, celery_app

    assert _beat_schedule, "beat schedule must not be empty"
    missing = [
        entry["task"] for entry in _beat_schedule.values() if entry["task"] not in celery_app.tasks
    ]
    assert missing == []
