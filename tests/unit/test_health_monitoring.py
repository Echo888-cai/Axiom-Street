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
