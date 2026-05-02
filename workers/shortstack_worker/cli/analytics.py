"""``shortstack-worker analytics ...`` subcommands."""

from __future__ import annotations

import json

import typer
from sqlalchemy import select

from shortstack_core.db import Niche, session_scope

from ..tasks import analytics as analytics_tasks

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command("snapshot")
def snapshot(
    publication_id: str = typer.Option(..., help="publication uuid"),
) -> None:
    """Pull a single MetricSnapshot for a publication."""
    result = analytics_tasks.snapshot_metrics.run(publication_id)
    typer.echo(json.dumps(result, indent=2, default=str))


@app.command("nightly-catchup")
def nightly_catchup() -> None:
    """Manually trigger the nightly catch-up (snapshots stale publications)."""
    result = analytics_tasks.nightly_catchup.run()
    typer.echo(json.dumps(result, indent=2, default=str))


@app.command("learnings")
def learnings(niche: str = typer.Option(..., help="niche slug")) -> None:
    """Synthesize this week's learnings.md for a niche (Sonnet)."""
    with session_scope() as s:
        n = s.execute(select(Niche).where(Niche.slug == niche)).scalar_one_or_none()
        if n is None:
            raise typer.BadParameter(f"niche slug not found: {niche}")
        niche_id = str(n.id)
    result = analytics_tasks.weekly_learnings.run(niche_id)
    typer.echo(json.dumps(result, indent=2, default=str))
