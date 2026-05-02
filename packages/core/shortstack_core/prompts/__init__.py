"""Prompt loader. Reads .md files alongside this module and returns their contents.

Prompt versioning: filename of the form ``<name>_v<n>.md``. Always load by full
filename so the version is explicit at the call site.

Niche-scoped learnings live in S3, not in the package, and are loaded via
``load_learnings(niche_id)``. They're produced by the weekly_learnings task
(Phase 6) and concatenated to the script-gen system prompt on the next run.
"""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
from uuid import UUID


@lru_cache(maxsize=64)
def load_prompt(name: str) -> str:
    """Load a prompt by filename (e.g. ``cluster_v1.md``)."""
    return files(__name__).joinpath(name).read_text(encoding="utf-8")


def learnings_key(niche_id: UUID | str) -> str:
    return f"niches/{niche_id}/learnings_v1.md"


def load_learnings(niche_id: UUID | str) -> str | None:
    """Load this niche's learnings markdown from S3, or None if not present.

    Failures (missing file, S3 error) are swallowed — the caller falls back to
    the base system prompt without learnings.
    """
    from ..storage import download_bytes

    try:
        return download_bytes(learnings_key(niche_id)).decode("utf-8")
    except Exception:  # noqa: BLE001 — best-effort prompt augmentation
        return None
