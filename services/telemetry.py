"""Shared Prometheus / OpenTelemetry / Sentry bootstrap (EB-P5).

Imported by both the API process and the Celery worker. Every SDK init is gated
on settings (``otel_enabled`` / ``sentry_dsn`` / ``prometheus_enabled``) so unit
tests — conftest disables all three — never dial out.

Tracer model: OpenTelemetry is the *single* tracer, exporting OTLP to a local
Jaeger. Sentry is errors-only (``traces_sample_rate=0``) to avoid double spans.
Prometheus metrics are collected on the API's ``/metrics`` endpoint; the worker
never runs its own HTTP exporter (Celery prefork children would fight over a
port), so API scrape-time aggregates broker queue depth + worker heartbeat age.
"""

from __future__ import annotations

import math
import time
from datetime import datetime, timezone

import prometheus_client
import structlog
from fastapi import FastAPI
from fastapi.responses import Response

from services.api.settings import get_settings

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Prometheus
# ---------------------------------------------------------------------------


class _PromMetrics:
    def __init__(self, registry: prometheus_client.CollectorRegistry) -> None:
        self.req_total = prometheus_client.Counter(
            "axiom_http_requests_total",
            "Total HTTP requests handled by the API.",
            ["method", "path", "status"],
            registry=registry,
        )
        self.req_duration = prometheus_client.Histogram(
            "axiom_http_request_duration_seconds",
            "HTTP request latency observed by the API.",
            ["method", "path"],
            buckets=(
                0.005,
                0.01,
                0.025,
                0.05,
                0.1,
                0.25,
                0.5,
                1.0,
                2.5,
                5.0,
                10.0,
                30.0,
                60.0,
                120.0,
                300.0,
            ),
            registry=registry,
        )
        self.queue_depth = prometheus_client.Gauge(
            "axiom_celery_queue_depth",
            "Messages currently waiting on the given Celery broker queue.",
            ["queue"],
            registry=registry,
        )
        self.worker_age = prometheus_client.Gauge(
            "axiom_worker_heartbeat_age_seconds",
            "Seconds since the worker last published its health heartbeat.",
            registry=registry,
        )
        self.worker_docker = prometheus_client.Gauge(
            "axiom_worker_docker_available",
            "1 when the worker reports Docker/LEAN available, 0 otherwise.",
            registry=registry,
        )


_metrics: _PromMetrics | None = None
_metrics_registry: prometheus_client.CollectorRegistry | None = None


def _ensure_metrics() -> _PromMetrics:
    global _metrics, _metrics_registry
    if _metrics is None:
        _metrics_registry = prometheus_client.CollectorRegistry(auto_describe=False)
        _metrics = _PromMetrics(_metrics_registry)
    return _metrics


def _refresh_process_gauges() -> None:
    """Best-effort scrape-time refreshes; every failure degrades to NaN, never raises."""
    import redis
    from redis import RedisError

    from services.worker.health import read_worker_health

    m = _ensure_metrics()

    health = read_worker_health()
    reported_at = health.get("reported_at") if isinstance(health, dict) else None
    age = math.nan
    if isinstance(reported_at, str):
        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(reported_at)).total_seconds()
        except ValueError:
            age = math.nan
    m.worker_age.set(age)
    docker_ok = bool(health.get("docker_available")) if isinstance(health, dict) else False
    m.worker_docker.set(1 if docker_ok else 0)

    try:
        broker = redis.Redis.from_url(
            get_settings().celery_broker_url,
            decode_responses=True,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
        )
        for queue in ("celery",):
            try:
                llen = broker.llen(queue)
            except RedisError:
                llen = None
            if isinstance(llen, int):  # type stubs also allow an Awaitable overload
                m.queue_depth.labels(queue=queue).set(float(llen))
            else:
                m.queue_depth.labels(queue=queue).set(math.nan)
        broker.connection_pool.disconnect()
    except RedisError:
        pass


def render_metrics() -> bytes:
    """Body for ``GET /metrics``. Empty (200) while metrics are disabled."""
    if not get_settings().prometheus_enabled:
        return b""
    _ensure_metrics()
    _refresh_process_gauges()
    assert _metrics_registry is not None
    return prometheus_client.generate_latest(_metrics_registry)


class PrometheusMiddleware:
    """Times every HTTP request into the Prometheus registry; inert when disabled."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or not get_settings().prometheus_enabled:
            await self.app(scope, receive, send)
            return
        m = _ensure_metrics()
        start = time.perf_counter()
        status = 500

        async def send_with_status(message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message.get("status", 500)
            await send(message)

        try:
            await self.app(scope, receive, send_with_status)
        finally:
            route = scope.get("route")
            path = getattr(route, "path", None) or str(scope.get("path", ""))
            method = str(scope.get("method", "")).upper()
            m.req_total.labels(method, path, str(status)).inc()
            m.req_duration.labels(method, path).observe(time.perf_counter() - start)


def register_metrics(app: FastAPI) -> None:
    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(content=render_metrics(), media_type="text/plain; version=0.0.4")


# ---------------------------------------------------------------------------
# OpenTelemetry — the single tracer, exported OTLP to a local Jaeger
# ---------------------------------------------------------------------------

_otel_started = False


def configure_otel(service_name: str, app: FastAPI | None = None) -> None:
    global _otel_started
    if _otel_started or not get_settings().otel_enabled:
        return
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.celery import CeleryInstrumentor
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=get_settings().otel_endpoint,
                insecure=True,
            )
        )
    )
    trace.set_tracer_provider(provider)

    # SQLAlchemy must be given the concrete engine to patch (no global hook).
    from services.api.db import engine as sqlalchemy_engine

    SQLAlchemyInstrumentor().instrument(engine=sqlalchemy_engine)
    CeleryInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
    if app is not None:
        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    _otel_started = True
    logger.info("opentelemetry enabled", service=service_name)


# ---------------------------------------------------------------------------
# Sentry — errors only (OTel owns tracing; traces_sample_rate stays 0)
# ---------------------------------------------------------------------------

_sentry_started = False


def configure_sentry() -> None:
    global _sentry_started
    dsn = get_settings().sentry_dsn
    if _sentry_started or not dsn:
        return
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.fastapi import FastApiIntegration

    sentry_sdk.init(
        dsn=dsn,
        integrations=[CeleryIntegration(), FastApiIntegration()],
        traces_sample_rate=0.0,
        send_default_pii=False,
    )
    _sentry_started = True
    logger.info("sentry enabled")


def capture_exception(exc: BaseException) -> None:
    if not get_settings().sentry_dsn:
        return
    import sentry_sdk

    sentry_sdk.capture_exception(exc)
