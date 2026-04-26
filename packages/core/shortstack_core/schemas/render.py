from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from .asset import AssetRef
from .script import ScriptDraft


class RenderJob(BaseModel):
    video_id: UUID
    script: ScriptDraft
    assets: list[AssetRef]
    output_key: str
