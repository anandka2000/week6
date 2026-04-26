"""Pydantic v2 schemas for every artifact that flows through the pipeline."""

from .asset import AssetRef, CaptionsDoc, Word
from .cost import CostEvent
from .metrics import MetricSnapshot
from .persona import NichePersona
from .publication import PublicationResult
from .render import RenderJob
from .script import Scene, ScriptDraft
from .trend import TrendCluster, TrendItem

__all__ = [
    "AssetRef",
    "CaptionsDoc",
    "CostEvent",
    "MetricSnapshot",
    "NichePersona",
    "PublicationResult",
    "RenderJob",
    "Scene",
    "ScriptDraft",
    "TrendCluster",
    "TrendItem",
    "Word",
]
