"""S3-compatible storage. MinIO locally, R2/S3 in prod (same boto3 client).

All artifacts for a video live under ``videos/{video_id}/...``::

    videos/{video_id}/scene_{i}.png       images
    videos/{video_id}/voice.mp3           tts
    videos/{video_id}/captions.json       word timings
    videos/{video_id}/output.mp4          render
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any
from uuid import UUID

import boto3
from botocore.client import Config

from .settings import get_settings


@lru_cache(maxsize=1)
def _client() -> Any:
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint_url,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        region_name=s.s3_region,
        config=Config(signature_version="s3v4"),
    )


def video_key(video_id: str | UUID, name: str) -> str:
    """Build the canonical s3 key for a per-video artifact."""
    return f"videos/{video_id}/{name}"


def upload_bytes(key: str, data: bytes, *, content_type: str) -> str:
    s = get_settings()
    _client().put_object(
        Bucket=s.s3_bucket, Key=key, Body=data, ContentType=content_type
    )
    return key


def download_bytes(key: str) -> bytes:
    s = get_settings()
    obj = _client().get_object(Bucket=s.s3_bucket, Key=key)
    return obj["Body"].read()


def signed_url(key: str, *, ttl_sec: int = 3600) -> str:
    s = get_settings()
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": s.s3_bucket, "Key": key},
        ExpiresIn=ttl_sec,
    )
