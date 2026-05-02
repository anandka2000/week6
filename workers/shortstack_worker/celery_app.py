"""Celery application factory.

One queue per phase: trends, scripts, assets, render, publish, analytics.
Tasks live under ``shortstack_worker.tasks``. Each task takes an ID
(never a raw payload) and is safe to retry.
"""

from __future__ import annotations

from celery import Celery
from kombu import Queue as KombuQueue

from shortstack_core.logging import configure_logging
from shortstack_core.settings import get_settings

from .queues import ALL_QUEUES, Queue

configure_logging()

settings = get_settings()

app = Celery(
    "shortstack",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "shortstack_worker.tasks.health",
        "shortstack_worker.tasks.trends",
        "shortstack_worker.tasks.scripts",
        "shortstack_worker.tasks.visuals",
        "shortstack_worker.tasks.tts",
        "shortstack_worker.tasks.captions",
        "shortstack_worker.tasks.assets",
        "shortstack_worker.tasks.render",
    ],
)

app.conf.update(
    task_default_queue=Queue.TRENDS.value,
    task_queues=tuple(KombuQueue(q) for q in ALL_QUEUES),
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    result_expires=3600,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_routes={
        "shortstack_worker.tasks.trends.*": {"queue": Queue.TRENDS.value},
        "shortstack_worker.tasks.scripts.*": {"queue": Queue.SCRIPTS.value},
        "shortstack_worker.tasks.assets.*": {"queue": Queue.ASSETS.value},
        "shortstack_worker.tasks.visuals.*": {"queue": Queue.ASSETS.value},
        "shortstack_worker.tasks.tts.*": {"queue": Queue.ASSETS.value},
        "shortstack_worker.tasks.captions.*": {"queue": Queue.ASSETS.value},
        "shortstack_worker.tasks.render.*": {"queue": Queue.RENDER.value},
        "shortstack_worker.tasks.publish.*": {"queue": Queue.PUBLISH.value},
        "shortstack_worker.tasks.analytics.*": {"queue": Queue.ANALYTICS.value},
    },
)

app.conf.beat_schedule = {
    # Phase 1+ will populate this. Keeping a marker so beat starts cleanly.
    "ping-every-5m": {
        "task": "shortstack_worker.tasks.health.ping",
        "schedule": 300.0,
    },
}
