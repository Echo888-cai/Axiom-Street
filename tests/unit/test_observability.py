from __future__ import annotations

import pytest
from pydantic import ValidationError

from services import telemetry
from services.api.settings import get_settings


def test_metrics_route_present_and_inert_when_disabled(client) -> None:
    """conftest disables Prometheus; GET /metrics must still 200 with an empty body."""
    res = client.get("/metrics")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/plain")
    assert res.content == b""


def test_render_metrics_exposes_axiom_series_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("STREET_PROMETHEUS_ENABLED", "true")
    get_settings.cache_clear()
    try:
        body = telemetry.render_metrics()
    finally:
        get_settings.cache_clear()
    assert b"axiom_http_requests_total" in body
    assert b"axiom_celery_queue_depth" in body
    assert b"axiom_worker_heartbeat_age_seconds" in body
    assert b"axiom_worker_docker_available" in body


def test_otel_and_sentry_are_noops_when_disabled(monkeypatch) -> None:
    """No DSN / otel disabled => init helpers must not raise and must not dial out."""
    monkeypatch.delenv("STREET_SENTRY_DSN", raising=False)
    monkeypatch.setenv("STREET_OTEL_ENABLED", "false")
    get_settings.cache_clear()
    try:
        telemetry.configure_otel("axiom-test")
        telemetry.configure_sentry()
    finally:
        get_settings.cache_clear()


def test_settings_reject_blank_database_url(monkeypatch) -> None:
    """The weak street:street default is gone; an empty URL must fail validation."""
    monkeypatch.setenv("STREET_DATABASE_URL", "")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValidationError):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_cors_origin_default_is_single_localhost_origin() -> None:
    settings = get_settings()
    assert settings.cors_origin_list == ["http://localhost:3000"]
