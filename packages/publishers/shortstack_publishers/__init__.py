"""ShortStack publishers — one ``Publisher`` per output platform."""

from .base import Publisher, PublishError, VideoMetadata
from .youtube import YouTubeShortsPublisher

__all__ = [
    "Publisher",
    "PublishError",
    "VideoMetadata",
    "YouTubeShortsPublisher",
]

__version__ = "0.1.0"
