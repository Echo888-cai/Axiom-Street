from celery import Celery
from celery.signals import worker_ready

from services.api.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "axiom_street",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["services.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    worker_concurrency=settings.worker_concurrency,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=settings.lean_timeout_seconds + 120,
    task_soft_time_limit=settings.lean_timeout_seconds + 60,
    beat_schedule={
        "reconcile-orphan-backtests": {
            "task": "backtests.reconcile_orphans",
            "schedule": 300.0,
        },
        "publish-worker-health": {
            "task": "worker.publish_health",
            "schedule": 15.0,
        },
    },
)


@worker_ready.connect
def _on_worker_ready(**_kwargs) -> None:
    from services.worker.health import publish_worker_health
    from services.worker.tasks import reconcile_orphan_backtests

    publish_worker_health()
    reconcile_orphan_backtests(worker_restart=True)
