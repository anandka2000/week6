"""Smoke tasks. Useful to confirm a queue is alive."""

from __future__ import annotations

from datetime import datetime, timezone

from shortstack_core.logging import get_logger

from ..celery_app import app

log = get_logger(__name__)


@app.task(name="shortstack_worker.tasks.health.ping")
def ping() -> dict[str, str]:
    now = datetime.now(tz=timezone.utc).isoformat()
    log.info("worker.ping", at=now)
    return {"status": "ok", "at": now}
