"""Celery app for async jobs (retraining, alerts, sentiment scraping)."""

from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery = Celery(
    "finpilot",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
)


@celery.task(name="health.ping")
def ping() -> str:
    """Trivial task to verify the worker is alive."""
    return "pong"
