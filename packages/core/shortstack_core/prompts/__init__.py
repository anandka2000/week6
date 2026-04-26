"""Prompt loader. Reads .md files alongside this module and returns their contents.

Prompt versioning: filename of the form ``<name>_v<n>.md``. Always load by full
filename so the version is explicit at the call site.
"""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import files


@lru_cache(maxsize=64)
def load_prompt(name: str) -> str:
    """Load a prompt by filename (e.g. ``cluster_v1.md``)."""
    return files(__name__).joinpath(name).read_text(encoding="utf-8")
