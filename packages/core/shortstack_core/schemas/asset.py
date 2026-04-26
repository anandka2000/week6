from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..enums import AssetKind


class Word(BaseModel):
    text: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)


class CaptionsDoc(BaseModel):
    words: list[Word]


class AssetRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: AssetKind
    scene_index: int | None = None
    provider: str
    s3_key: str
    meta: dict[str, Any] = Field(default_factory=dict)
