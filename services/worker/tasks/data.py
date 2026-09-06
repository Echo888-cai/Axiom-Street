"""Data-domain Celery tasks: symbol ingest and scheduled market reconcile."""

from __future__ import annotations

from services.worker.celery_app import celery_app


@celery_app.task(name="data.ingest")
def run_ingest_task(job_id: str) -> dict:
    from services.api.services.ingest_jobs import execute_ingest_job

    return execute_ingest_job(job_id)


@celery_app.task(name="data.reconcile_market")
def reconcile_market_data_task(force: bool = False) -> dict:
    """Periodic full re-pull of the current universe to catch vendor restatements."""
    from services.api.services.ingest_jobs import schedule_market_reconcile

    return schedule_market_reconcile(force=force, scheduled=True)
