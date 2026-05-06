"""Trend tasks: fetch (per source) + cluster (Haiku) + pick.

Every task takes a ``niche_id`` and is idempotent. ``raw_payload`` is preserved
so we can re-cluster historical data without re-fetching.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from shortstack_core.cost import record_llm
from shortstack_core.db import Niche, Trend, session_scope
from shortstack_core.enums import TrendSource
from shortstack_core.llm import call as llm_call
from shortstack_core.llm import extract_json
from shortstack_core.prompts import load_prompt
from shortstack_core.schemas import NichePersona, TrendItem

from ..celery_app import app  # noqa: F401  (ensures app is registered)
from ..sources.reddit import fetch_subreddit_hot

log = get_task_logger(__name__)

CLUSTER_PROMPT_VERSION = "cluster_v1"
TREND_RECENCY_HOURS = 48


@shared_task(
    name="shortstack_worker.tasks.trends.fetch_reddit",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=4,
    acks_late=True,
)
def fetch_reddit(niche_id: str) -> dict[str, Any]:
    """Pull hot posts from each subreddit listed on the niche persona."""
    niche_uuid = UUID(niche_id)
    written = 0

    with session_scope() as s:
        niche = s.get(Niche, niche_uuid)
        if niche is None:
            raise ValueError(f"niche {niche_id} not found")
        persona = NichePersona.model_validate(niche.persona_json)
        if not persona.subreddits:
            log.warning("niche %s has no subreddits configured", niche_id)
            return {"niche_id": niche_id, "written": 0, "subreddits": []}

        for sub in persona.subreddits:
            items = fetch_subreddit_hot(sub, limit=25)
            log.info("reddit.fetch sub=%s n=%d", sub, len(items))
            for item in items:
                stmt = (
                    pg_insert(Trend)
                    .values(
                        id=uuid.uuid4(),
                        niche_id=niche_uuid,
                        source=item.source.value,
                        external_id=item.external_id,
                        title=item.title,
                        url=str(item.url) if item.url else None,
                        summary=item.summary,
                        raw_payload=item.raw,
                        fetched_at=item.fetched_at,
                    )
                    .on_conflict_do_nothing(
                        index_elements=["source", "external_id"]
                    )
                )
                result = s.execute(stmt)
                if result.rowcount:
                    written += 1

    return {"niche_id": niche_id, "written": written, "subreddits": persona.subreddits}


@shared_task(
    name="shortstack_worker.tasks.trends.cluster",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=2,
    acks_late=True,
)
def cluster(niche_id: str) -> dict[str, Any]:
    """Run Haiku over recent unconsumed trends and stamp cluster_id + hook_score."""
    niche_uuid = UUID(niche_id)
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=TREND_RECENCY_HOURS)

    with session_scope() as s:
        niche = s.get(Niche, niche_uuid)
        if niche is None:
            raise ValueError(f"niche {niche_id} not found")

        rows = (
            s.execute(
                select(Trend)
                .where(Trend.niche_id == niche_uuid)
                .where(Trend.fetched_at >= cutoff)
                .where(Trend.consumed_at.is_(None))
                .where(Trend.cluster_id.is_(None))
            )
            .scalars()
            .all()
        )
        if not rows:
            log.info("cluster: no unclustered trends for niche=%s", niche_id)
            return {"niche_id": niche_id, "clustered": 0}

        compact = [
            {
                "external_id": r.external_id,
                "source": r.source.value if hasattr(r.source, "value") else r.source,
                "title": r.title,
                "summary": (r.summary or "")[:200],
            }
            for r in rows
        ]

        system = load_prompt("cluster_v1.md")
        user = json.dumps({"items": compact}, ensure_ascii=False)

        resp = llm_call(
            model="claude-haiku-4-5",
            system=system,
            user=user,
            max_tokens=2048,
            cache_system=True,
        )
        record_llm(
            s,
            niche_id=niche_uuid,
            model=resp.usage.model,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            cache_read_tokens=resp.usage.cache_read_tokens,
            cache_write_tokens=resp.usage.cache_write_tokens,
            meta={"prompt_version": CLUSTER_PROMPT_VERSION, "task": "cluster"},
        )

        try:
            parsed = extract_json(resp.text)
        except ValueError as exc:
            # Surface the raw response so the operator can see what Haiku said
            # — celery's autoretry would otherwise re-raise without context.
            log.error(
                "cluster.invalid_json",
                extra={
                    "niche_id": niche_id,
                    "input_tokens": resp.usage.input_tokens,
                    "output_tokens": resp.usage.output_tokens,
                    "raw_text": resp.text[:1000],
                },
            )
            raise ValueError(
                f"cluster: Haiku response wasn't parseable JSON. "
                f"Tokens: in={resp.usage.input_tokens} out={resp.usage.output_tokens}. "
                f"Raw text (truncated): {resp.text[:300]!r}. "
                f"Original error: {exc}"
            ) from exc
        clusters = parsed.get("clusters", [])

        clustered = 0
        for c in clusters:
            cluster_id = uuid.uuid4()
            score = int(c.get("hook_score", 0))
            for ext_id in c.get("member_external_ids", []):
                s.execute(
                    update(Trend)
                    .where(Trend.niche_id == niche_uuid)
                    .where(Trend.external_id == ext_id)
                    .values(cluster_id=cluster_id, hook_score=score)
                )
                clustered += 1

    return {"niche_id": niche_id, "clusters": len(clusters), "clustered": clustered}


@shared_task(name="shortstack_worker.tasks.trends.pick_next")
def pick_next(niche_id: str) -> dict[str, Any] | None:
    """Pick the highest-scored unconsumed trend in the recency window."""
    niche_uuid = UUID(niche_id)
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=TREND_RECENCY_HOURS)

    with session_scope() as s:
        row = s.execute(
            select(Trend)
            .where(Trend.niche_id == niche_uuid)
            .where(Trend.fetched_at >= cutoff)
            .where(Trend.consumed_at.is_(None))
            .where(Trend.hook_score.is_not(None))
            .order_by(Trend.hook_score.desc(), Trend.fetched_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        if row is None:
            return None

        row.consumed_at = datetime.now(tz=timezone.utc)
        return {
            "trend_id": str(row.id),
            "external_id": row.external_id,
            "title": row.title,
            "hook_score": row.hook_score,
        }
