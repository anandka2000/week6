"""Celery queue names. Imported anywhere we declare or route a task."""

from __future__ import annotations

from enum import Enum


class Queue(str, Enum):
    TRENDS = "trends"
    SCRIPTS = "scripts"
    ASSETS = "assets"
    RENDER = "render"
    PUBLISH = "publish"
    ANALYTICS = "analytics"


ALL_QUEUES: tuple[str, ...] = tuple(q.value for q in Queue)
