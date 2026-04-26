"""``shortstack-worker trends ...`` subcommands. Run inline (no Celery hop)."""

from __future__ import annotations

import json

import typer
from sqlalchemy import select

from shortstack_core.db import Niche, session_scope

from ..tasks import trends as trend_tasks

app = typer.Typer(no_args_is_help=True, add_completion=False)


def _niche_id_by_slug(slug: str) -> str:
    with session_scope() as s:
        niche = s.execute(select(Niche).where(Niche.slug == slug)).scalar_one_or_none()
        if niche is None:
            raise typer.BadParameter(f"niche slug not found: {slug}")
        return str(niche.id)


@app.command("fetch")
def fetch(niche: str = typer.Option(..., help="niche slug")) -> None:
    """Fetch fresh Reddit posts for a niche."""
    result = trend_tasks.fetch_reddit.run(_niche_id_by_slug(niche))
    typer.echo(json.dumps(result, indent=2, default=str))


@app.command("cluster")
def cluster(niche: str = typer.Option(..., help="niche slug")) -> None:
    """Cluster + score recent unconsumed trends with Haiku."""
    result = trend_tasks.cluster.run(_niche_id_by_slug(niche))
    typer.echo(json.dumps(result, indent=2, default=str))


@app.command("pick")
def pick(niche: str = typer.Option(..., help="niche slug")) -> None:
    """Pick (and consume) the top-scored trend."""
    result = trend_tasks.pick_next.run(_niche_id_by_slug(niche))
    typer.echo(json.dumps(result, indent=2, default=str))
