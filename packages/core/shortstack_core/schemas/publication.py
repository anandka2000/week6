from __future__ import annotations

from typing import Any

from pydantic import BaseModel, HttpUrl

from ..enums import Platform, Visibility


class PublicationResult(BaseModel):
    platform: Platform
    external_id: str
    external_url: HttpUrl
    visibility: Visibility
    raw: dict[str, Any] = {}
