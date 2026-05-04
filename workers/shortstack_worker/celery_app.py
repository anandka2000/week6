"""Celery application factory.

One queue per phase: trends, scripts, assets, render, publish, analytics.
Tasks live under ``shortstack_worker.tasks``. Each task takes an ID
(never a raw payload) and is safe to retry.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab
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
        "shortstack_worker.tasks.publish",
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
    "ping-every-5m": {
        "task": "shortstack_worker.tasks.health.ping",
        "schedule": 300.0,
    },
    # Catch any publication whose latest snapshot is >24h old. Belt-and-suspenders
    # for the t+24h/72h/7d ETAs scheduled at publish time.
    "analytics-nightly-catchup": {
        "task": "shortstack_worker.tasks.analytics.nightly_catchup",
        "schedule": crontab(hour=2, minute=0),
    },
    # Sunday 02:00 UTC: synthesize learnings.md per niche from last week's data.
    "analytics-weekly-learnings": {
        "task": "shortstack_worker.tasks.analytics.weekly_learnings_all",
        "schedule": crontab(day_of_week="sunday", hour=2, minute=0),
    },
    # Phase 9: 10:00 UTC daily — produce up to niches.daily_quota videos per
    # niche. Auto-approve heuristic in render_video gates which ones skip
    # /review. 1h gap before publish_approved_all gives the operator a
    # chance to reject before the upload fires.
    "automation-daily-pipeline": {
        "task": "shortstack_worker.tasks.automation.daily_pipeline_all",
        "schedule": crontab(hour=10, minute=0),
    },
    # Phase 9: 11:00 UTC daily — publish APPROVED videos that don't yet have
    # a YouTube Publication. Visible in /review for the 1h gap so an operator
    # can flip them back to FAILED if the heuristic was wrong.
    "automation-publish-approved": {
        "task": "shortstack_worker.tasks.automation.publish_approved_all",
        "schedule": crontab(hour=11, minute=0),
    },
}
