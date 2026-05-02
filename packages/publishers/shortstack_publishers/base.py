"""Publisher contract.

Each platform has its own ``Publisher`` implementation. The worker
``publish_video`` task picks the right one based on ``Publication.platform``.
Publishers are stateless and idempotent on the ``(video_id, platform)`` pair.

The contract is deliberately narrow: ``publish(video_bytes, metadata) ->
PublicationResult``. The publisher does not see the DB, does not know about
videos, and does not retry on its own — those concerns live in the worker
task.
"""

from __future__ import annotations

import abc

from pydantic import BaseModel, Field

from shortstack_core.enums import Platform, Visibility
from shortstack_core.schemas import PublicationResult


class VideoMetadata(BaseModel):
    """Platform-agnostic upload metadata. Each publisher maps it to its own shape."""

    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=5000)
    tags: list[str] = Field(default_factory=list)
    visibility: Visibility = Visibility.UNLISTED
    category_id: str = "28"  # YouTube: Science & Technology
    contains_synthetic_media: bool = True
    made_for_kids: bool = False


class PublishError(Exception):
    """Raised when a publish call fails. Wraps the underlying error so the
    worker can roll status back without leaking httpx internals."""

    def __init__(
        self, platform: Platform, message: str, *, cause: Exception | None = None
    ):
        self.platform = platform
        self.cause = cause
        super().__init__(f"publish to {platform.value} failed: {message}")


class Publisher(abc.ABC):
    """Stateless publisher. Subclasses set ``platform`` and implement ``publish``."""

    platform: Platform

    @abc.abstractmethod
    def publish(self, video_bytes: bytes, metadata: VideoMetadata) -> PublicationResult:
        """Upload ``video_bytes`` with the given metadata. Return the persisted
        ``PublicationResult`` shape (which the worker writes into the
        ``publications`` table)."""
